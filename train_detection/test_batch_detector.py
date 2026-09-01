"""The batching must not change what a camera sees, only when it sees it."""

import threading
import time

import numpy as np
import pytest

import batch_detector
from batch_detector import BatchDetector


class _FakeBox:
    def __init__(self, conf, xyxy, cls=0):
        self.conf = conf
        self.xyxy = [xyxy]
        self.cls = cls


class _FakeResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeModel:
    """Records the batch sizes it was asked for."""

    names = {0: 'train'}

    def __init__(self):
        self.calls = []

    def predict(self, frames, **_kwargs):
        self.calls.append(len(frames))
        time.sleep(0.01)
        # one box per frame, its score encoded from the frame's first pixel
        return [_FakeResult([_FakeBox(float(f[0][0]) / 100,
                                      (0, 0, 10, 10))]) for f in frames]


@pytest.fixture
def detector(monkeypatch):
    model = _FakeModel()
    monkeypatch.setattr(BatchDetector, '__init__',
                        lambda self, *a, **k: None)
    d = BatchDetector.__new__(BatchDetector)
    d.model = model
    d.names = model.names
    d.classes = None
    d.device = 'cpu'
    d._pending = []
    d._wake = threading.Condition()
    d._stop = False
    d._batches = 0
    d._frames = 0
    d._worker = threading.Thread(target=d._run, daemon=True)
    d._worker.start()
    yield d, model
    d.close()


def _frame(value):
    return np.full((2, 2), value, dtype=np.uint8)


def test_every_caller_gets_its_own_result(detector):
    """The risk of batching is handing one camera another camera's train."""
    d, _model = detector
    got = {}

    def ask(value):
        got[value] = d.trains(_frame(value), conf=0.0)

    threads = [threading.Thread(target=ask, args=(v,)) for v in (10, 20, 30, 40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert set(got) == {10, 20, 30, 40}
    for value, result in got.items():
        assert result[0][0] == pytest.approx(value / 100, abs=1e-3)


def test_concurrent_callers_share_one_model_call(detector):
    d, model = detector
    threads = [threading.Thread(target=lambda: d.trains(_frame(50), conf=0.0))
               for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Six callers, far fewer than six calls — the whole point.
    assert max(model.calls) > 1
    assert len(model.calls) < 6


def test_a_lone_caller_is_not_left_waiting(detector):
    d, _model = detector
    start = time.perf_counter()
    d.trains(_frame(70), conf=0.0)
    # Must not hold out for a full batch that will never arrive.
    assert time.perf_counter() - start < 0.2


def test_a_stricter_caller_does_not_inherit_a_looser_threshold(detector):
    """A batch runs at the lowest conf asked for; each caller re-filters."""
    d, _model = detector
    assert d.trains(_frame(30), conf=0.5) == []      # 0.30 < 0.5
    assert d.trains(_frame(80), conf=0.5) != []      # 0.80 >= 0.5
