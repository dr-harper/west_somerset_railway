"""Tests for track-centreline geometry.

Uses a synthetic camera whose track is an L-shape, so the two limbs have
very different tangents — the case a single per-camera direction vector
cannot represent, and the reason this module exists.
"""

import pytest

import track_geometry as tg

# Straight limb east, then a limb turning south: like a curve at a station
L_TRACK = {'points': [[100, 100], [300, 100], [400, 200], [400, 400]]}


@pytest.fixture(autouse=True)
def synthetic_track(monkeypatch):
    monkeypatch.setitem(tg.TRACKS, 'test_cam', L_TRACK)
    yield
    tg.TRACKS.pop('test_cam', None)


class TestProjection:
    def test_point_on_track_has_no_offset(self):
        placed = tg.project('test_cam', (200, 100))
        assert placed['offset_px'] == pytest.approx(0, abs=0.5)

    def test_offset_measures_distance_from_the_rails(self):
        placed = tg.project('test_cam', (200, 140))
        assert placed['offset_px'] == pytest.approx(40, abs=1)

    def test_arc_length_grows_along_the_track(self):
        near = tg.project('test_cam', (150, 100))
        far = tg.project('test_cam', (400, 300))
        assert far['arc_px'] > near['arc_px']
        assert 0 <= near['arc_normalised'] <= 1

    def test_unknown_camera_returns_nothing(self):
        assert tg.project('no_such_cam', (0, 0)) is None


class TestLocalTangent:
    """The point of the module: tangent varies along the track."""

    def test_tangent_differs_between_limbs(self):
        first = tg.project('test_cam', (200, 100))['tangent_to_minehead']
        second = tg.project('test_cam', (400, 300))['tangent_to_minehead']
        assert first == pytest.approx((1.0, 0.0), abs=0.01)   # heading east
        assert second == pytest.approx((0.0, 1.0), abs=0.01)  # heading south

    def test_same_motion_reads_differently_on_each_limb(self):
        """Rightward motion is northbound on one limb, unclear on the other."""
        drift = (60, 0)
        assert tg.direction_of_motion('test_cam', (200, 100), drift) == 'northbound'
        assert tg.direction_of_motion('test_cam', (400, 300), drift) == 'unclear'

    def test_direction_reverses_with_motion(self):
        assert tg.direction_of_motion('test_cam', (200, 100), (-60, 0)) == 'southbound'
        assert tg.direction_of_motion('test_cam', (400, 300), (0, 60)) == 'northbound'
        assert tg.direction_of_motion('test_cam', (400, 300), (0, -60)) == 'southbound'

    def test_tiny_motion_is_unclear(self):
        assert tg.direction_of_motion('test_cam', (200, 100), (3, 1)) == 'unclear'

    def test_motion_across_the_track_is_unclear(self):
        # a person crossing the line, not a train running along it
        assert tg.direction_of_motion('test_cam', (200, 100), (0, 80)) == 'unclear'


class TestAnchors:
    def test_no_anchors_means_no_mileage(self):
        assert tg.arc_to_miles('test_cam', 100) is None

    def test_two_anchors_map_arc_length_to_miles(self):
        tg.TRACKS['test_cam'] = {
            **L_TRACK,
            'anchors': [
                {'point': [100, 100], 'miles': 10.0},
                {'point': [300, 100], 'miles': 10.5},
            ],
        }
        assert tg.arc_to_miles('test_cam', 0) == pytest.approx(10.0, abs=0.01)
        assert tg.arc_to_miles('test_cam', 200) == pytest.approx(10.5, abs=0.01)
