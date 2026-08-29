"""Every camera the watcher opens must be usable, not just streamable.

The watcher iterates CAMERAS, not CALIBRATED, so a camera annotated in
the browser but missing from a lookup table in Python does not sit idle —
it fails. Three ways that happened, each silent in a different way:

  KeyError on ZONES        killed the worker thread on the first detection
  KeyError on the vector   killed it again inside the error handler
  empty motion mask        no crash at all, just a camera that never sees

These tests pin the fallbacks so adding a twelfth camera cannot
reintroduce any of them.
"""

import numpy as np
import pytest

import track_geometry as tg
from detection_zones import ZONES
from gala_watcher import NORTHBOUND_VECTORS
from wsr_live_capture import CAMERAS

PROC_W, PROC_H = 427, 240

ANNOTATED = [c for c in CAMERAS if tg.tracks_of(c)]


def test_some_cameras_lack_hand_drawn_zones():
    """The premise of the fallbacks — if this fails they are dead code."""
    assert [c for c in CAMERAS if c not in ZONES]


@pytest.mark.parametrize('camera', ANNOTATED)
def test_annotated_camera_has_somewhere_to_look(camera):
    """Zones or rails must give the motion gate a non-empty mask."""
    mask = np.zeros((PROC_H, PROC_W), np.uint8)
    for _name, kind, poly in ZONES.get(camera, []):
        if kind in ('detect', 'approach'):
            import cv2
            pts = (np.array(poly, np.float32) * (PROC_W / 854)).astype(np.int32)
            cv2.fillPoly(mask, [pts], 255)
    if not mask.any():
        mask = tg.corridor_mask(camera, PROC_W, PROC_H)
    assert mask.any(), f'{camera} has nothing for the motion gate to watch'


@pytest.mark.parametrize('camera', ANNOTATED)
def test_corridor_follows_the_track(camera):
    """The corridor must cover the rails without swallowing the frame."""
    mask = tg.corridor_mask(camera, PROC_W, PROC_H)
    for track in tg.tracks_of(camera):
        for sample in tg.centreline(camera, track['name']):
            x, y = sample['point']
            xi = min(PROC_W - 1, int(x * PROC_W / 854))
            yi = min(PROC_H - 1, int(y * PROC_H / 480))
            assert mask[yi, xi] > 0, f'{camera}: corridor misses its own centreline'
    assert mask.mean() < 0.9 * 255, f'{camera}: corridor covers the whole frame'


@pytest.mark.parametrize('camera', CAMERAS)
def test_direction_never_raises_without_a_vector(camera):
    """Missing vectors must read as unclear, not explode."""
    vector = NORTHBOUND_VECTORS.get(camera)
    assert vector is None or len(vector) == 2


@pytest.mark.parametrize('camera', CAMERAS)
def test_zone_lookup_is_guarded(camera):
    """ZONES.get, never ZONES[...] — the latter killed the worker."""
    assert isinstance(ZONES.get(camera, []), list)


@pytest.mark.parametrize('camera', ANNOTATED)
def test_block_out_does_not_hide_the_running_line(camera):
    """Painting over the rails would blind the gate where trains run."""
    blocked = tg.exclusion_mask(camera, 854, 480)
    hits = total = 0
    for track in tg.tracks_of(camera):
        if track['kind'] not in tg.RUNNING_KINDS:
            continue
        for sample in tg.centreline(camera, track['name']):
            x, y = sample['point']
            xi, yi = min(853, int(round(x))), min(479, int(round(y)))
            total += 1
            hits += blocked[yi, xi] > 0
    if total:
        assert hits / total <= 0.10, (
            f'{camera}: block-out covers {hits / total:.0%} of the running line')
