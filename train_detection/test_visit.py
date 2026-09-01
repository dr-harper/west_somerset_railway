"""A station visit must come apart into the movements worth recording."""

from visit import Kind, State, Visit


def feed(visit, samples, start=0.0, step=1.0):
    """samples: string of '-' away, 'M' moving, 'S' standing."""
    out = []
    for i, mark in enumerate(samples):
        out += visit.observe(start + i * step,
                             present=mark != '-',
                             moving=mark == 'M')
    return out


def test_a_train_that_arrives_waits_and_leaves_is_three_events():
    """The Blue Anchor case: 618 seconds recorded as one thing."""
    visit = Visit()
    feed(visit, '---MMMMMSSSSSSSSSSMMMMM---')
    kinds = [e.kind for e in visit.events]
    assert Kind.ARRIVAL in kinds
    assert Kind.DWELL in kinds
    assert Kind.DEPARTURE in kinds
    assert kinds.index(Kind.ARRIVAL) < kinds.index(Kind.DWELL) < kinds.index(Kind.DEPARTURE)


def test_a_train_that_does_not_stop_is_one_passage():
    visit = Visit()
    feed(visit, '---MMMMMMMM---')
    visit.finish(20.0)
    assert [e.kind for e in visit.events] == [Kind.PASSAGE]


def test_a_standing_train_produces_no_movement():
    """469 of 618 seconds were this, and none of it is worth recording."""
    visit = Visit()
    feed(visit, '--SSSSSSSSSSSS--')
    assert [e.kind for e in visit.events] == [Kind.DWELL]
    assert visit.summary()['moving_s'] == 0


def test_a_single_quiet_sample_does_not_end_a_movement():
    """A train easing to a stand crosses the threshold repeatedly."""
    visit = Visit()
    feed(visit, '---MMMSMMMSMMMSSSSSS')
    assert [e.kind for e in visit.events].count(Kind.ARRIVAL) == 1


def test_a_single_twitch_does_not_end_a_dwell():
    visit = Visit()
    feed(visit, '--SSSSMSSSSSSS')
    assert Kind.DEPARTURE not in [e.kind for e in visit.events]


def test_departure_needs_the_train_to_have_stood_first():
    """Otherwise every clip that opens mid-movement reads as a departure."""
    visit = Visit()
    feed(visit, 'MMMMMMM---')
    assert [e.kind for e in visit.events] == [Kind.PASSAGE]


def test_summary_separates_time_worth_watching_from_time_that_is_not():
    visit = Visit()
    feed(visit, '--MMMMSSSSSSSSSSSSMMMM--', step=10.0)
    s = visit.summary()
    assert s['arrivals'] == 1 and s['departures'] == 1
    assert s['dwell_s'] > s['moving_s']


def test_finish_closes_whatever_was_open():
    visit = Visit()
    feed(visit, '--MMMM')
    assert visit.state is State.MOVING
    closed = visit.finish(99.0)
    assert closed and closed[0].ended == 99.0
