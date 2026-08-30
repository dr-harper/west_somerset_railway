"""Tests for deriving exclusion masks from a run's own false gates."""

import propose_exclusions as pe


ALL = {'blue_anchor': {10: 40, 11: 30, 50: 12, 99: 2}}
FALSE = {'blue_anchor': {10: 40, 11: 29, 50: 2, 99: 2}}


class TestProposal:
    def test_a_cell_that_never_finds_a_train_is_proposed(self):
        cells = pe.propose('blue_anchor', ALL, FALSE, min_events=5)
        assert 10 in cells

    def test_a_cell_that_usually_finds_trains_is_kept(self):
        cells = pe.propose('blue_anchor', ALL, FALSE, min_events=5)
        assert 50 not in cells, 'this cell yields trains 10 of 12 times'

    def test_one_train_is_enough_to_keep_a_cell(self):
        # 29 of 30 wasted, but the one that was not is a train that would
        # go unseen. At Blue Anchor on 30/8 95% of gates were false, so a
        # ratio rule proposed the running line itself.
        cells = pe.propose('blue_anchor', ALL, FALSE, min_events=5)
        assert 11 not in cells

    def test_rare_cells_are_not_judged(self):
        # seen twice, wasted twice — but two events is not evidence
        cells = pe.propose('blue_anchor', ALL, FALSE, min_events=5)
        assert 99 not in cells

    def test_traced_track_is_never_proposed(self):
        # A camera with traced rails must keep every cell they pass through,
        # whatever the gate log says about them.
        protected = pe.track_cells('blue_anchor')
        assert protected, 'blue_anchor has traced roads'
        busy = {'blue_anchor': {cell: 50 for cell in protected}}
        assert pe.propose('blue_anchor', busy, busy, min_events=5) == []

    def test_an_unknown_camera_proposes_nothing(self):
        assert pe.propose('nowhere', ALL, FALSE, 5) == []


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
