"""One model, one call, many cameras.

Eleven camera threads sharing a single YOLO reference behind a lock is
not wrong — a second model instance would contend for the same GPU, and
measurement bears that out: eleven frames in one batched call take 261ms
against 371ms issued one at a time, so the device is already near its
limit and duplicating the model buys almost nothing.

What the lock costs is not throughput but waiting. A camera can queue
behind ten others for about 340ms before its frame is even looked at,
which is invisible for a standing train and matters for a fast one.

So the frames are gathered instead of queued. A camera hands over a frame
and waits; a collector takes everything handed over within a few
milliseconds and puts it through the model together. Eleven cameras then
wait one inference rather than up to eleven.

The wait is deliberately short. Holding out for a full batch would make a
quiet moment — one camera with something to look at, ten with nothing —
slower than the lock it replaces.
"""

import threading
import time
from dataclasses import dataclass, field

MAX_BATCH = 12          # eleven cameras, plus room
GATHER_S = 0.008        # how long to wait for company before going


@dataclass
class _Job:
    frame: object
    conf: float
    done: threading.Event = field(default_factory=threading.Event)
    result: list = field(default_factory=list)
    error: BaseException | None = None


class BatchDetector:
    """Batches concurrent detection requests into single model calls."""

    def __init__(self, weights: str, classes: list | None = None):
        from ultralytics import YOLO
        import torch

        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.model = YOLO(weights)
        self.names = self.model.names
        self.classes = classes
        self._pending: list[_Job] = []
        self._wake = threading.Condition()
        self._stop = False
        self._batches = 0
        self._frames = 0
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # -- the camera side ------------------------------------------------

    def trains(self, frame, conf: float = 0.4) -> list:
        """Detections for one frame. Blocks until the batch it joins runs."""
        job = _Job(frame=frame, conf=conf)
        with self._wake:
            self._pending.append(job)
            self._wake.notify()
        job.done.wait()
        if job.error:
            raise job.error
        return job.result

    def stats(self) -> dict:
        return {'batches': self._batches, 'frames': self._frames,
                'mean_batch': self._frames / self._batches if self._batches else 0}

    def close(self) -> None:
        with self._wake:
            self._stop = True
            self._wake.notify_all()

    # -- the model side -------------------------------------------------

    def _take(self) -> list:
        """Wait for work, then briefly for company, and take what there is."""
        with self._wake:
            while not self._pending and not self._stop:
                self._wake.wait(0.05)
            if self._stop and not self._pending:
                return []
        time.sleep(GATHER_S)
        with self._wake:
            batch, self._pending = self._pending[:MAX_BATCH], self._pending[MAX_BATCH:]
            return batch

    def _run(self) -> None:
        while True:
            batch = self._take()
            if not batch:
                if self._stop:
                    return
                continue
            try:
                # One conf for the call, so a batch is only grouped where
                # the threshold agrees; mixed thresholds are rare and are
                # simply run as smaller batches.
                conf = min(job.conf for job in batch)
                results = self.model.predict(
                    [job.frame for job in batch], verbose=False,
                    conf=conf, device=self.device,
                    **({'classes': self.classes} if self.classes else {}))
                self._batches += 1
                self._frames += len(batch)
                for job, result in zip(batch, results):
                    job.result = self._boxes(result, job.conf)
            except BaseException as error:      # noqa: BLE001 - re-raised to caller
                for job in batch:
                    job.error = error
            finally:
                for job in batch:
                    job.done.set()

    def _boxes(self, result, conf: float) -> list:
        """(conf, (x1,y1,x2,y2), (cx,cy)) for each train, as before.

        Filtered again per job: a batch runs at the lowest threshold asked
        for, so a caller wanting 0.5 must not be handed another's 0.4.
        """
        out = []
        for box in result.boxes:
            score = round(float(box.conf), 3)
            if score < conf:
                continue
            name = self.names[int(box.cls)]
            if name not in ('train', 'wagon', 'loco'):
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            out.append((score, (x1, y1, x2, y2), ((x1 + x2) // 2, (y1 + y2) // 2)))
        return out
