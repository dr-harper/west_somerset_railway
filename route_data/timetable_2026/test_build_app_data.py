"""Tests for the timetable transform script.

Run from this directory: pytest test_build_app_data.py
"""

import json
from pathlib import Path

from build_app_data import (
    direction_of,
    modal_id_to_date,
    parse_cell,
    parse_service_table,
    title_to_family,
)

HERE = Path(__file__).parent


class TestParseCell:
    def test_colon_time(self):
        assert parse_cell('10:15') == ('10:15', False)

    def test_space_time(self):
        assert parse_cell('10 15') == ('10:15', False)

    def test_crossing_time(self):
        # 'x' means trains cross at this station — still a public call
        assert parse_cell('10x28') == ('10:28', True)

    def test_passing_time_is_not_a_call(self):
        # '//' timings are photographic only; the train does not stop
        assert parse_cell('08//32') == (None, False)

    def test_non_calls(self):
        for raw in ['-', '', 'STOP', 'START', 'x', '–']:
            assert parse_cell(raw) == (None, False)

    def test_single_digit_hour(self):
        assert parse_cell('9 30') == ('09:30', False)


class TestTitleToFamily:
    def test_plain_families(self):
        assert title_to_family('Red Timetable (2 Steam) 2026', None) == 'red'
        assert title_to_family('Blue Timetable 2026 (All Diesels)', None) == 'blue'

    def test_reduced_does_not_match_red(self):
        # regression: '(Reduced)' contains the substring 'red'
        assert title_to_family('Yellow Timetable (Reduced) 2026', None) == 'yellow'

    def test_date_named_timetable(self):
        assert title_to_family('12.08 - Timetable 2026', None) == 'yellow'

    def test_event_titles(self):
        assert title_to_family('Diesels @ 65 - Saturday', None) == 'purple'
        assert title_to_family('Christmas', None) == 'green'


class TestDates:
    def test_2026_months(self):
        assert modal_id_to_date('august-01') == '2026-08-01'
        assert modal_id_to_date('december-24') == '2026-12-24'

    def test_january_rolls_to_2027(self):
        assert modal_id_to_date('january-02') == '2027-01-02'


class TestDirection:
    def test_northbound_towards_minehead(self):
        assert direction_of(['BL', 'CH', 'MIN']) == 'NB'

    def test_southbound_from_minehead(self):
        assert direction_of(['MIN', 'DUN', 'BL']) == 'SB'


class TestGoldenDay:
    """Parse a real scraped day and pin the expected output."""

    def _services(self, modal_id):
        raw = json.loads((HERE / 'day_timetables_raw.json').read_text())
        services = []
        for table in raw[modal_id]['tables']:
            if table and table[0] and table[0][0].strip() == 'Key':
                continue
            services.extend(parse_service_table(table))
        return services

    def test_standard_blue_day(self):
        services = self._services('september-01')
        assert len(services) == 8
        nb = [s for s in services if s['direction'] == 'NB']
        assert len(nb) == 4
        first = nb[0]
        assert first['serviceType'] == 'Steam'
        assert first['stops'][0] == {'c': 'BL', 'a': None, 'd': '10:15'}
        assert first['stops'][-1]['c'] == 'MIN'
        assert first['stops'][-1]['a'] == '11:35'

    def test_gala_day_short_working(self):
        services = self._services('august-29')
        # the 11:35 ex-Bishops Lydeard terminates at Williton
        short = [s for s in services
                 if s['stops'][0]['d'] == '11:35' and s['stops'][0]['c'] == 'BL']
        assert short and short[0]['stops'][-1]['c'] == 'WIL'

    def test_gala_day_arrival_departure_merge(self):
        # duplicate station rows merge into one arrive/depart call
        services = self._services('august-29')
        for service in services:
            codes = [s['c'] for s in service['stops']]
            assert len(codes) == len(set(codes)), f'duplicate stop in {codes}'
