"""Tests for physics-based movement chaining and identity gating."""

from movement_tracker import (build_movements, distance_miles, transit_window,
                              _identity_compatible)


def episode(camera, hhmmss, direction='unclear', conf=0.9):
    return {'camera': camera, 't_enter': f'2026-08-29T{hhmmss}',
            't_exit': f'2026-08-29T{hhmmss}', 'direction': direction,
            'peak_conf': conf, 'drift_px': None}


class TestLineGeometry:
    def test_distance_is_symmetric(self):
        assert round(distance_miles('BL', 'MIN'), 1) == round(distance_miles('MIN', 'BL'), 1)

    def test_whole_line_is_about_twenty_miles(self):
        assert 18 <= distance_miles('BL', 'MIN') <= 23

    def test_transit_window_brackets_line_speed(self):
        low, high = transit_window('BL', 'CH')
        assert low < high
        assert 5 <= low <= 15      # ~3.8 miles at 30mph
        assert high <= 40


class TestChaining:
    def test_plausible_transit_chains(self):
        # Crowcombe -> Watchet is 7.7 miles; 30 minutes is ~15mph
        moves = build_movements([
            episode('crowcombe_heathfield', '10:00:00'),
            episode('watchet_visitor_centre', '10:30:00'),
        ])
        through = [m for m in moves if m['sightings'] > 1]
        assert len(through) == 1
        assert through[0]['direction'] == 'northbound'

    def test_impossibly_fast_does_not_chain(self):
        # 7.7 miles in two minutes is not a train
        moves = build_movements([
            episode('crowcombe_heathfield', '10:00:00'),
            episode('watchet_visitor_centre', '10:02:00'),
        ])
        assert all(m['sightings'] == 1 for m in moves)

    def test_far_apart_in_time_does_not_chain(self):
        moves = build_movements([
            episode('crowcombe_heathfield', '10:00:00'),
            episode('watchet_visitor_centre', '13:00:00'),
        ])
        assert all(m['sightings'] == 1 for m in moves)

    def test_direction_is_fixed_by_the_first_link(self):
        # a train does not run north then double back south mid-journey
        moves = build_movements([
            episode('crowcombe_heathfield', '10:00:00'),
            episode('watchet_visitor_centre', '10:30:00'),
            episode('bishops_lydeard', '11:05:00'),
        ])
        longest = max(moves, key=lambda m: m['sightings'])
        stations = [o['station'] for o in longest['observations']]
        assert stations == ['CH', 'WAT']

    def test_repeat_sightings_at_one_camera_merge(self):
        # stock standing in a platform detected repeatedly is one occupancy
        moves = build_movements([
            episode('minehead_station', '10:00:00'),
            episode('minehead_station', '10:04:00'),
            episode('minehead_station', '10:09:00'),
        ])
        assert len(moves) == 1


class TestIdentityGate:
    def test_unknown_identity_never_blocks(self):
        assert _identity_compatible(None, {'traction': 'steam'})
        assert _identity_compatible({'traction': 'steam'}, None)

    def test_traction_mismatch_blocks(self):
        assert not _identity_compatible({'traction': 'steam'}, {'traction': 'diesel'})

    def test_number_beats_traction(self):
        a, b = {'traction': 'diesel', 'number': 'D7017'}, {'traction': 'diesel', 'number': 'D6566'}
        assert not _identity_compatible(a, b)

    def test_identity_splits_an_otherwise_valid_chain(self):
        """The payoff: two same-class locos are ambiguous by timing alone."""
        eps = [episode('crowcombe_heathfield', '10:00:00'),
               episode('watchet_visitor_centre', '10:30:00')]
        assert max(build_movements(eps), key=lambda m: m['sightings'])['sightings'] == 2

        identities = {'2026-08-29T10:00:00': {'traction': 'steam'},
                      '2026-08-29T10:30:00': {'traction': 'diesel'}}
        split = build_movements(eps, identities)
        assert all(m['sightings'] == 1 for m in split)
