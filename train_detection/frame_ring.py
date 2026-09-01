"""Every frame the stream delivers, kept for a while, with its real time.

The run-up to a train was sampled at 10fps from inside the loop that also
does motion detection and YOLO, so it could only ever be taken as fast as
that loop went round. On 31/8 that was one frame every five seconds: the
pre-roll written into each clip was twelve frames — half a second where
twenty-five seconds was intended — and what little there was came from
10fps material dropped into a 25fps file, which is the jump at the start
of every recording.

Two things follow from that and both are fixed here rather than tuned.

Recording must not be a passenger of analysis. The ring is filled by a
thread that does nothing else, so a slow inference pass costs detection
latency and never costs frames.

Frames must carry their own time. The writer assumed 25fps while the
streams delivered anywhere between 4 and 41, so every clip played at the
wrong speed and every measurement taken in seconds from one was wrong.
Knowing the rate before the file is opened is what lets it be written
honestly.

Held as JPEG because raw does not fit: a frame is 1.23MB against 120KB
encoded, so eleven cameras would want gigabytes to keep the same seconds.
Encoding costs 0.7ms, which at stream rate across the line is about a
sixth of one core.

Times come from the stream, not from the clock on the wall. A live HLS
feed hands over a whole segment at once and the decoder runs through it as
fast as it can — measured against one camera, frames arrived 0.000s apart
while the media clock advanced a steady 0.033s. Timestamping on arrival
made a 30fps stream look like a thousand, which would have set a clip's
frame rate to 956fps had a sanity check not caught it. What matters is
when the railway did something, and only the media clock knows that.
"""

import threading
import time
from collections import deque

import cv2

# Measured against a live camera rather than guessed: the streams run at
# 30fps and a frame encodes to about 143KB, so a second of one camera costs
# 4.3MB and fifteen seconds across eleven cameras is about 700MB — near
# nothing on a 64GB machine. The window is the run-up a clip opens with, so
# it wants to be longer than the delay between a train arriving and the
# watcher noticing; it can shrink as that delay is measured and reduced.
DEFAULT_SECONDS = 15.0
DEFAULT_QUALITY = 70
# A stream that bursts or loses its clock must not be able to take the
# machine down with it.
MAX_FRAMES = 1200


class FrameRing:
    """The last `seconds` of one camera, timestamped.

    Safe to fill from one thread and read from another, which is the whole
    point: the reader never waits for anything the analysis is doing.
    """

    def __init__(self, seconds: float = DEFAULT_SECONDS,
                 quality: int = DEFAULT_QUALITY,
                 max_frames: int = MAX_FRAMES):
        self.seconds = seconds
        self.quality = quality
        self.max_frames = max_frames
        self._frames: deque = deque()       # (when, jpeg bytes)
        self._lock = threading.Lock()
        self._latest = None                 # (when, raw frame)
        self.added = 0
        self.dropped = 0

    # -- filling --------------------------------------------------------

    def add(self, when: float, frame) -> bool:
        """Keep a frame, timed by the stream's own clock.

        `when` must be media time. Wall-clock arrival is not usable: a
        burst of buffered frames all land at the same instant.
        """
        ok, encoded = cv2.imencode(
            '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            return False
        with self._lock:
            self._latest = (when, frame)
            self._frames.append((when, encoded.tobytes()))
            self.added += 1
            # Trimmed by age rather than by count, so the window means the
            # same number of seconds whatever the stream is managing.
            cutoff = when - self.seconds
            while self._frames and self._frames[0][0] < cutoff:
                self._frames.popleft()
                self.dropped += 1
            while len(self._frames) > self.max_frames:
                self._frames.popleft()
                self.dropped += 1
        return True

    # -- reading --------------------------------------------------------

    def latest(self):
        """The newest frame, undecoded, for whatever wants to look at it."""
        with self._lock:
            return self._latest

    def tail(self, seconds: float, until: float | None = None) -> list:
        """(when, jpeg) for the last `seconds`, oldest first."""
        with self._lock:
            if not self._frames:
                return []
            end = until if until is not None else self._frames[-1][0]
            start = end - seconds
            return [(w, j) for w, j in self._frames if start <= w <= end]

    def rate(self, window: float = 5.0) -> float:
        """Frames per second the stream is actually delivering.

        Measured rather than assumed. A clip opened at this rate plays at
        the speed the railway moved at, which no clip written before today
        did.
        """
        recent = self.tail(window)
        if len(recent) < 2:
            return 0.0
        span = recent[-1][0] - recent[0][0]
        return (len(recent) - 1) / span if span > 0 else 0.0

    def span(self) -> float:
        """How many seconds of history are actually held."""
        with self._lock:
            if len(self._frames) < 2:
                return 0.0
            return self._frames[-1][0] - self._frames[0][0]

    def nbytes(self) -> int:
        with self._lock:
            return sum(len(j) for _w, j in self._frames)

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)


class StreamReader(threading.Thread):
    """Pulls frames off a capture and drops them in the ring, and nothing else.

    Kept apart from the analysis so that a camera falling behind on
    inference loses detection latency and not its recording. That was the
    trap in the old loop: once a pass took longer than its own cadence,
    every iteration became a heavy one and the run-up collapsed with it.
    """

    def __init__(self, name: str, ring: FrameRing, open_capture, on_error=None):
        super().__init__(name=f'reader-{name}', daemon=True)
        self.camera = name
        self.ring = ring
        self.open_capture = open_capture
        self.on_error = on_error
        self.cap = None
        self.running = True
        self.reconnects = 0
        self.last_frame_at = 0.0
        # The stream's clock restarts at zero on every reconnect, so an
        # offset carries the timeline forward and the ring is not flushed
        # by a stream that merely blinked.
        self._epoch = 0.0
        self._last_media = 0.0

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        backoff = 2
        while self.running:
            try:
                if self.cap is None:
                    self.cap = self.open_capture()
                    if self.cap is None:
                        raise RuntimeError('no capture')
                    backoff = 2
                if not self.cap.grab():
                    raise RuntimeError('stream read failed')
                ok, frame = self.cap.retrieve()
                if not ok:
                    raise RuntimeError('retrieve failed')
                media = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if media <= 0:
                    # No media clock: fall back to the wall, which is wrong
                    # about bursts but better than no timeline at all.
                    media = time.time() - self._epoch
                when = self._epoch + media
                if when < self._last_media:
                    # The stream restarted. Carry on from where we were
                    # rather than jumping backwards.
                    self._epoch = self._last_media
                    when = self._epoch + media
                self._last_media = when
                self.ring.add(when, frame)
                self.last_frame_at = time.time()
            except Exception as error:      # noqa: BLE001 - reported, not raised
                self.reconnects += 1
                self._epoch = self._last_media
                if self.on_error:
                    self.on_error(error)
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
