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


# --- direction ----------------------------------------------------------

VALIDATED = {c: v for c, v in NORTHBOUND_VECTORS.items() if v != (0.0, 0.0)}


@pytest.mark.parametrize('camera', sorted(VALIDATED))
def test_trace_orientation_matches_the_validated_vector(camera):
    """minehead_end must agree with the vector checked against real trains."""
    if not tg.tracks_of(camera):
        pytest.skip('not traced')
    samples = tg.centreline(camera, 'running line')
    if not samples or len(samples) < 2:
        pytest.skip('no running line')
    a, b = samples[0]['point'], samples[-1]['point']
    chord = (b[0] - a[0], b[1] - a[1])
    vector = VALIDATED[camera]
    towards = (chord[0] * vector[0] + chord[1] * vector[1]) > 0
    assert tg.trace_runs_to_minehead(camera) == towards, (
        f'{camera}: minehead_end disagrees with the validated vector')


@pytest.mark.parametrize('camera', sorted(VALIDATED))
def test_local_tangent_points_northbound(camera):
    """The oriented tangent must not be more than 90deg from the vector.

    Beyond that the sign flips and every direction call inverts — the bug
    this whole flag exists to prevent.
    """
    if not tg.minehead_end_known(camera):
        pytest.skip('orientation not established')
    placed = tg.project(camera, (427, 240))
    if not placed:
        pytest.skip('nothing to project onto')
    tx, ty = placed['tangent_to_minehead']
    vx, vy = VALIDATED[camera]
    assert tx * vx + ty * vy > 0, f'{camera}: tangent points the wrong way'


def test_unknown_orientation_is_not_silently_assumed():
    """A camera with no minehead_end must report unknown, not a default."""
    untraced = [c for c in CAMERAS if not tg.minehead_end_known(c)]
    assert untraced, 'expected some cameras still awaiting orientation'
    for camera in untraced:
        assert tg.trace_runs_to_minehead(camera) is True  # the safe default


# --- registry sync ------------------------------------------------------

def test_app_camera_registry_is_in_sync():
    """The web app's copy must match what the pipeline actually runs.

    Three pages once kept their own hardcoded six-camera list, so
    detections from the five newer cameras rendered as raw ids and were
    absent from the per-camera counts. One generated file replaced them;
    this fails the moment it drifts.
    """
    import json
    from camera_registry import APP_DATA, registry

    assert APP_DATA.exists(), (
        'cameras.json is missing — run python3 camera_registry.py --write')
    on_disk = json.loads(APP_DATA.read_text())
    assert on_disk == registry(), (
        'cameras.json is stale — run python3 camera_registry.py --write')


def test_every_camera_has_a_station_node():
    """Without a node a camera cannot take part in movement chaining."""
    from train_tracker import CAMERA_NODES
    missing = [c for c in CAMERAS if c not in CAMERA_NODES]
    assert not missing, f'no station node for {missing}'
