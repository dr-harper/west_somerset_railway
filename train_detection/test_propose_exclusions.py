"""Tests for deriving exclusion masks from a run's own false gates."""

import propose_exclusions as pe


ALL = {'blue_anchor': {10: 40, 11: 30, 50: 12, 99: 2}}
FALSE = {'blue_anchor': {10: 40, 11: 29, 50: 2, 99: 2}}


class TestProposal:
    def test_a_cell_that_never_finds_a_train_is_proposed(self):
        cells = pe.propose('blue_anchor', ALL, FALSE, min_ratio=0.95, min_events=5)
        assert 10 in cells

    def test_a_cell_that_usually_finds_trains_is_kept(self):
        cells = pe.propose('blue_anchor', ALL, FALSE, min_ratio=0.95, min_events=5)
        assert 50 not in cells, 'this cell yields trains 10 of 12 times'

    def test_rare_cells_are_not_judged(self):
        # seen twice, wasted twice — but two events is not evidence
        cells = pe.propose('blue_anchor', ALL, FALSE, min_ratio=0.95, min_events=5)
        assert 99 not in cells

    def test_the_threshold_is_adjustable(self):
        loose = pe.propose('blue_anchor', ALL, FALSE, min_ratio=0.9, min_events=5)
        assert 11 in loose, 'wasted 29 of 30 — excluded at 0.9, not at 0.95'

    def test_an_unknown_camera_proposes_nothing(self):
        assert pe.propose('nowhere', ALL, FALSE, 0.95, 5) == []


class TestGeometry:
    def test_cells_map_to_distinct_boxes(self):
        first = pe.cell_box(0)
        next_along = pe.cell_box(1)
        next_row = pe.cell_box(pe.MOTION_GRID_W)
        assert first[0] < next_along[0], 'cell 1 sits to the right of cell 0'
        assert first[1] < next_row[1], 'the next row sits below'

    def test_the_grid_covers_the_frame(self):
        last = pe.cell_box(pe.MOTION_GRID_W * pe.MOTION_GRID_H - 1)
        assert last[0] + last[2] <= pe.FRAME_W
        assert last[1] + last[3] <= pe.FRAME_H

    def test_regions_are_annotator_shaped(self):
        region = pe.as_regions([0])[0]
        assert region['kind'] == 'exclude'
        assert len(region['points']) == 4
        assert region['auto'] is True
