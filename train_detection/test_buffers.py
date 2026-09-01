"""Nothing the watcher keeps for later is held uncompressed.

Two buffers held raw frames: twelve seconds of them for the review clip's
run-up, and up to three hundred more during an episode. At stream rate that
is roughly 800MB for a single active camera, which is why the process sat at
2GB and grew with traffic. On a laptop that is untidy; in a container with a
hard limit it is how a morning gets lost.
"""

import numpy as np

from gala_watcher import encode_frame


def frame(value=120):
    return np.full((480, 854, 3), value, dtype=np.uint8)


def test_a_kept_frame_is_bytes_not_pixels():
    encoded = encode_frame(frame())
    assert isinstance(encoded, (bytes, bytearray))


def test_encoding_is_worth_doing():
    raw = frame()
    encoded = encode_frame(raw)
    assert len(encoded) < raw.nbytes / 5, (
        f'{raw.nbytes / 1024:.0f}KB raw vs {len(encoded) / 1024:.0f}KB encoded')


def test_three_hundred_kept_frames_stay_under_a_hundred_megabytes():
    """The cap that used to allow 370MB."""
    import cv2
    # A busy frame rather than flat colour, so the size is not flattering.
    rng = np.random.default_rng(0)
    busy = rng.integers(0, 255, (480, 854, 3), dtype=np.uint8)
    busy = cv2.GaussianBlur(busy, (7, 7), 0)      # photographic, not noise
    encoded = encode_frame(busy)
    assert len(encoded) * 300 < 100 * 1024 * 1024


def test_an_unencodable_frame_gives_nothing_rather_than_raising():
    assert encode_frame(np.zeros((0, 0, 3), np.uint8)) is None
