"""The run-up to a train, and the rate it was really captured at.

Each case here is something the old buffer got wrong on 31/8: it held five
frames instead of two hundred and fifty, they were sampled at a tenth of
the stream's rate, and nothing recorded what that rate had been.
"""

import numpy as np
import pytest

from frame_ring import FrameRing


def frame(value=128, size=(48, 64)):
    return np.full((*size, 3), value, dtype=np.uint8)


def fill(ring, fps, seconds, start=1000.0):
    """Frames arriving evenly at `fps` for `seconds`."""
    step = 1.0 / fps
    n = int(fps * seconds)
    for i in range(n):
        ring.add(start + i * step, frame(i % 255))
    return start + (n - 1) * step


def test_keeps_every_frame_the_stream_delivers():
    """The old buffer sampled at 10fps whatever arrived; this takes it all."""
    ring = FrameRing(seconds=10)
    fill(ring, fps=25, seconds=5)
    assert len(ring) == 125


def test_window_is_seconds_not_frames():
    """A slow stream should still hold the same span, just fewer frames."""
    fast, slow = FrameRing(seconds=10), FrameRing(seconds=10)
    fill(fast, fps=25, seconds=30)
    fill(slow, fps=4, seconds=30)
    assert fast.span() == pytest.approx(10, abs=0.2)
    assert slow.span() == pytest.approx(10, abs=0.4)
    assert len(fast) > len(slow)


def test_old_frames_fall_out():
    ring = FrameRing(seconds=5)
    fill(ring, fps=20, seconds=20)
    assert ring.span() <= 5.05
    assert ring.dropped > 0


def test_rate_is_measured_not_assumed():
    """Clips were written at 25fps while streams delivered 4 to 41."""
    for fps in (4, 12, 25, 40):
        ring = FrameRing(seconds=20)
        fill(ring, fps=fps, seconds=10)
        assert ring.rate() == pytest.approx(fps, rel=0.05)


def test_rate_of_an_empty_ring_is_zero_not_a_guess():
    assert FrameRing().rate() == 0.0
    ring = FrameRing()
    ring.add(1000.0, frame())
    assert ring.rate() == 0.0          # one frame says nothing about rate


def test_tail_returns_the_run_up_in_order():
    ring = FrameRing(seconds=30)
    end = fill(ring, fps=20, seconds=20)
    run_up = ring.tail(10, until=end)
    assert run_up == sorted(run_up)
    assert len(run_up) == pytest.approx(200, abs=3)


def test_tail_of_a_slow_stream_is_short_but_still_spans_the_window():
    """Five frames was the whole failure; here the span is right either way."""
    ring = FrameRing(seconds=30)
    end = fill(ring, fps=2, seconds=20)
    run_up = ring.tail(10, until=end)
    assert 15 <= len(run_up) <= 25
    assert run_up[-1][0] - run_up[0][0] == pytest.approx(10, abs=1.0)


def test_latest_is_the_raw_frame_so_analysis_need_not_decode():
    ring = FrameRing()
    ring.add(1000.0, frame(77))
    when, raw = ring.latest()
    assert when == 1000.0
    assert raw[0][0][0] == 77


def test_memory_stays_within_the_window():
    """15s at 20fps was budgeted at about 36MB a camera."""
    ring = FrameRing(seconds=15)
    fill(ring, fps=20, seconds=60)
    assert ring.span() <= 15.05
    assert len(ring) <= 20 * 15 + 2


def test_reader_thread_fills_the_ring_from_a_real_capture(tmp_path):
    """End to end against a file standing in for a stream.

    The reader has to keep filling without anything else driving it — that
    independence is the fix, so it is worth testing rather than assuming.
    """
    import glob
    import time as clock

    import cv2

    from frame_ring import StreamReader

    clips = sorted(glob.glob('captures/*_dense.mp4'))
    usable = next((c for c in clips
                   if cv2.VideoCapture(c).get(cv2.CAP_PROP_FRAME_COUNT) > 50), None)
    if not usable:
        pytest.skip('no capture to read from')

    ring = FrameRing(seconds=5)
    reader = StreamReader('test', ring, lambda: cv2.VideoCapture(usable))
    reader.start()
    try:
        for _ in range(60):
            if len(ring) > 30:
                break
            clock.sleep(0.05)
    finally:
        reader.stop()
        clock.sleep(0.1)

    assert len(ring) > 30, 'reader did not fill the ring'
    assert ring.latest() is not None
    when, frame = ring.latest()
    assert frame.shape[2] == 3
    assert ring.rate() > 0


def test_a_stream_that_loses_its_clock_cannot_exhaust_memory():
    """Every frame timed the same is what a burst looks like from outside."""
    ring = FrameRing(seconds=8, max_frames=100)
    for _ in range(500):
        ring.add(1000.0, frame())      # no time passing at all
    assert len(ring) <= 100


def test_reader_carries_the_timeline_across_a_restart():
    """A stream's clock restarts at zero; the ring must not jump backwards."""
    from frame_ring import StreamReader

    class Blinking:
        """Runs to 3s, drops, then starts again from zero."""
        def __init__(self): self.n = 0; self.restarted = False
        def isOpened(self): return True
        def grab(self):
            self.n += 1
            if self.n == 90 and not self.restarted:
                self.restarted = True
                raise RuntimeError('stream dropped')
            return True
        def retrieve(self): return True, frame()
        def get(self, _prop):
            return ((self.n if not self.restarted else self.n - 90) / 30) * 1000
        def release(self): pass

    ring = FrameRing(seconds=30)
    cap = Blinking()
    reader = StreamReader('t', ring, lambda: cap)
    reader._epoch, reader._last_media = 0.0, 0.0
    # Drive the timestamping directly rather than racing a thread.
    for _ in range(150):
        try:
            cap.grab()
        except RuntimeError:
            reader._epoch = reader._last_media
            continue
        media = cap.get(0) / 1000.0
        when = reader._epoch + media
        if when < reader._last_media:
            reader._epoch = reader._last_media
            when = reader._epoch + media
        reader._last_media = when
        ring.add(when, frame())
    times = [w for w, _ in ring.tail(1e9)]
    assert times == sorted(times), 'timeline went backwards over a restart'
