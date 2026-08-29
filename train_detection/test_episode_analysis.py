"""Tests for episode -> timetable matching.

Run from this directory: pytest test_episode_analysis.py
Uses the real generated timetable2026.json as fixture data.
"""

from episode_analysis import match_episode


def episode(camera, t_enter, direction):
    return {'camera': camera, 't_enter': t_enter, 'direction': direction}


class TestGalaDayMatching:
    """2026-08-29 is the Diesels @ 65 gala — a real service-heavy day."""

    def test_matches_departure_within_tolerance(self):
        m = match_episode(episode('bishops_lydeard', '2026-08-29T10:16:30', 'northbound'))
        assert not m['is_special']
        assert m['match']['time'] == '10:15'
        assert m['match_gap_min'] == 1.5

    def test_direction_must_agree(self):
        # at 10:16 there is a 10:15 NB call; a southbound episode must not take it
        m = match_episode(episode('bishops_lydeard', '2026-08-29T10:16:30', 'southbound'))
        assert m['match'] is None or m['match']['direction'] == 'southbound'

    def test_unclear_direction_still_matches(self):
        m = match_episode(episode('minehead_station', '2026-08-29T11:33:00', 'unclear'))
        assert not m['is_special']
        assert m['match']['time'] == '11:35'


class TestSpecialDetection:
    def test_night_movement_is_special(self):
        m = match_episode(episode('watchet_visitor_centre', '2026-08-29T03:00:00', 'southbound'))
        assert m['is_special']

    def test_closed_day_movement_is_special(self):
        # 2026-08-28 was a closed day: any confirmed movement is unscheduled
        m = match_episode(episode('crowcombe_heathfield', '2026-08-28T12:00:00', 'northbound'))
        assert m['is_special']

    def test_far_outside_tolerance_is_special(self):
        # 30+ minutes from any scheduled call
        m = match_episode(episode('crowcombe_heathfield', '2026-09-01T09:00:00', 'northbound'))
        assert m['is_special']


class TestNonStopPasses:
    def test_gala_pass_is_not_special(self):
        # the 08:20 ex-Bishops Lydeard passes Crowcombe non-stop at 08//32
        m = match_episode(episode('crowcombe_heathfield', '2026-08-29T08:33:04', 'unclear'))
        assert not m['is_special']
        assert m['match']['passes'] is True
        assert m['match']['time'] == '08:32'


class TestStationMapping:
    def test_seaward_crossing_maps_to_minehead(self):
        m = match_episode(episode('minehead_seaward_crossing', '2026-08-29T03:00:00', 'northbound'))
        assert m['station'] == 'MIN'
