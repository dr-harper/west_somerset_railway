"""Tests for rail-pair track geometry.

The synthetic camera looks along a track that runs east then turns south,
with the rails converging as they recede — so the fixture exercises both
things a single traced line cannot represent: a changing tangent, and a
changing scale.
"""

import math

import pytest

import track_geometry as tg

# Rails 100px apart near the camera, narrowing to 20px as they recede,
# turning a corner half way along.
CURVED_PAIR = {
    'rails': {
        'a': [[100, 340], [300, 330], [420, 290], [470, 200], [478, 120]],
        'b': [[100, 460], [300, 420], [452, 340], [500, 225], [502, 138]],
    }
}
# A straight track with parallel rails: no perspective, constant scale.
FLAT_PAIR = {
    'rails': {
        'a': [[100, 200], [700, 200]],
        'b': [[100, 300], [700, 300]],
    }
}
# A station throat: a running line with a siding beside it, as at
# Minehead or the Seaward Crossing.
TWO_ROADS = {
    'tracks': [
        {'name': 'platform road', 'kind': 'running',
         'rails': {'a': [[100, 200], [700, 200]], 'b': [[100, 300], [700, 300]]}},
        {'name': 'goods siding', 'kind': 'siding',
         'rails': {'a': [[100, 400], [700, 400]], 'b': [[100, 500], [700, 500]]}},
    ]
}


@pytest.fixture(autouse=True)
def synthetic(monkeypatch):
    monkeypatch.setitem(tg.TRACKS, 'curved', CURVED_PAIR)
    monkeypatch.setitem(tg.TRACKS, 'flat', FLAT_PAIR)
    monkeypatch.setitem(tg.TRACKS, 'yard', TWO_ROADS)
    tg._CENTRELINE_CACHE.clear()
    yield
    for name in ('curved', 'flat', 'yard'):
        tg.TRACKS.pop(name, None)
    tg._CENTRELINE_CACHE.clear()


class TestRailPair:
    def test_a_single_rail_is_not_enough(self):
        tg.TRACKS['lonely'] = {'rails': {'a': [[0, 0], [10, 10]], 'b': []}}
        assert tg.rails_of('lonely') is None
        tg.TRACKS.pop('lonely')

    def test_centreline_runs_between_the_rails(self):
        samples = tg.centreline('flat')
        assert all(abs(s['point'][1] - 250) < 1 for s in samples)

    def test_gauge_is_the_rail_separation(self):
        placed = tg.project('flat', (400, 250))
        assert placed['gauge_px'] == pytest.approx(100, abs=1)


class TestScaleFromGauge:
    def test_known_gauge_gives_metres_per_pixel(self):
        placed = tg.project('flat', (400, 250))
        # 100px between rails that are 1.435 m apart
        assert placed['metres_per_px'] == pytest.approx(tg.STANDARD_GAUGE_M / 100, rel=0.02)

    def test_scale_changes_with_depth_on_a_perspective_view(self):
        near = tg.project('curved', (150, 400))
        far = tg.project('curved', (500, 140))
        assert near['gauge_px'] > far['gauge_px']
        # the same pixel motion covers more ground further away
        assert far['metres_per_px'] > near['metres_per_px'] * 1.5

    def test_flat_view_has_constant_scale(self):
        a = tg.project('flat', (200, 250))['metres_per_px']
        b = tg.project('flat', (600, 250))['metres_per_px']
        assert a == pytest.approx(b, rel=0.02)


class TestLocalTangent:
    def test_tangent_follows_the_curve(self):
        first = tg.project('curved', (200, 390))['tangent_to_minehead']
        last = tg.project('curved', (500, 140))['tangent_to_minehead']
        # east along the first limb, mostly north up the second
        assert first[0] > 0.8
        assert last[1] < -0.5

    def test_direction_uses_the_tangent_where_the_train_is(self):
        assert tg.direction_of_motion('curved', (200, 390), (60, 0)) == 'northbound'
        assert tg.direction_of_motion('curved', (200, 390), (-60, 0)) == 'southbound'
        # the same rightward motion means nothing on the second limb
        assert tg.direction_of_motion('curved', (500, 140), (60, 0)) == 'unclear'

    def test_motion_across_the_rails_is_not_travel(self):
        assert tg.direction_of_motion('flat', (400, 250), (0, 70)) == 'unclear'

    def test_tiny_motion_is_unclear(self):
        assert tg.direction_of_motion('flat', (400, 250), (4, 0)) == 'unclear'


class TestSpeed:
    def test_speed_uses_the_local_scale(self):
        # 100px in 2s on the flat pair: 100 * 0.01435 m = 1.435 m -> 0.72 m/s
        path = [[0.0, 300, 250], [2.0, 400, 250]]
        mph = tg.speed_mph('flat', path)
        expected = (100 * tg.STANDARD_GAUGE_M / 100) / 2.0 * 2.23694
        assert mph == pytest.approx(expected, rel=0.05)

    def test_similar_pixel_motion_is_faster_further_away(self):
        """Sixty pixels near the camera is a crawl; sixty in the distance
        is a real speed. Ignoring perspective would call them equal."""
        near = tg.speed_mph('curved', [[0.0, 150, 395], [2.0, 210, 393]])
        far = tg.speed_mph('curved', [[0.0, 470, 172], [2.0, 478, 113]])
        assert far > near * 2

    def test_a_single_sample_has_no_speed(self):
        assert tg.speed_mph('flat', [[0.0, 100, 250]]) is None


class TestVanishingPoint:
    def test_converging_rails_have_one(self):
        vp = tg.vanishing_point('curved')
        assert vp is not None and all(math.isfinite(v) for v in vp)

    def test_parallel_rails_have_none(self):
        assert tg.vanishing_point('flat') is None


class TestOnTrack:
    def test_a_point_on_the_rails_is_on_track(self):
        assert tg.project('flat', (400, 250))['on_track']

    def test_something_well_beside_the_line_is_not(self):
        # four gauges off the centreline: beside the railway, not on it
        assert not tg.project('flat', (400, 650))['on_track']


class TestMultipleTracks:
    """A camera usually sees several roads; a detection belongs to one."""

    def test_legacy_single_pair_still_loads(self):
        tracks = tg.tracks_of('flat')
        assert len(tracks) == 1
        assert tracks[0]['kind'] == 'running'

    def test_every_traced_road_is_listed(self):
        names = [t['name'] for t in tg.tracks_of('yard')]
        assert names == ['platform road', 'goods siding']

    def test_a_train_is_attributed_to_the_road_it_stands_on(self):
        on_platform = tg.project('yard', (400, 250))
        in_siding = tg.project('yard', (400, 450))
        assert on_platform['track'] == 'platform road'
        assert in_siding['track'] == 'goods siding'

    def test_running_line_and_siding_are_distinguished(self):
        assert tg.project('yard', (400, 250))['is_running_line']
        assert not tg.project('yard', (400, 450))['is_running_line']

    def test_the_runner_up_road_is_reported(self):
        placed = tg.project('yard', (400, 250))
        assert placed['alternatives'][0]['track'] == 'goods siding'

    def test_a_clear_attribution_is_not_ambiguous(self):
        assert not tg.project('yard', (400, 250))['ambiguous']

    def test_a_point_between_two_roads_is_flagged_ambiguous(self):
        # midway between the platform road and the siding
        assert tg.project('yard', (400, 350))['ambiguous']

    def test_offset_is_measured_in_gauges_not_pixels(self):
        placed = tg.project('yard', (400, 250))
        assert placed['offset_gauges'] == pytest.approx(0, abs=0.05)

    def test_speed_can_be_pinned_to_one_road(self):
        path = [[0.0, 300, 250], [2.0, 400, 250]]
        assert tg.speed_mph('yard', path, track='platform road') is not None
