"""A train at a station is two movements and a wait, not one long event.

An episode used to run from the moment a train appeared to the moment it
left, so a train that stopped produced one record covering everything.
Blue Anchor 2 on 31/8 held a single episode for 618 seconds of which 469
were a stationary rake, its direction recorded as 'unclear' because the
train had gone both ways within it, and the dense clip fired on the
arrival so the departure was never captured at stream rate at all.

What actually happens has three parts, and only two of them are worth
watching:

    arrival    a movement that ends at rest
    dwell      a span of time in which nothing moves
    departure  a movement that begins at rest

A train that does not stop is a passage, and is one movement.

Movement is judged from the train's own pixels, not from a box centre,
which drifts as the detector changes its mind about where a train ends.
Both edges are held over several samples: a train easing to a stand
crosses the threshold repeatedly before settling, and a single quiet
sample must not close a movement that is still under way.
"""

from dataclasses import dataclass, field
from enum import Enum

# How many consecutive samples decide a change of state. At roughly 1Hz
# this is a couple of seconds either way, which is slower than a train
# stops and faster than anyone cares about.
SETTLE = 3


class State(Enum):
    AWAY = 'away'            # nothing here
    MOVING = 'moving'
    STANDING = 'standing'


class Kind(Enum):
    ARRIVAL = 'arrival'      # movement that ended at rest
    DEPARTURE = 'departure'  # movement that began at rest
    PASSAGE = 'passage'      # movement with no rest either side
    DWELL = 'dwell'          # the wait between


@dataclass
class Event:
    kind: Kind
    started: float
    ended: float

    @property
    def seconds(self) -> float:
        return self.ended - self.started

    def __repr__(self) -> str:
        return f'{self.kind.value}({self.started:.0f}-{self.ended:.0f}s)'


@dataclass
class Visit:
    """Segments one camera's view of a train into movements and waits."""

    state: State = State.AWAY
    events: list = field(default_factory=list)
    _since: float | None = None          # when the current state began
    _run: int = 0                        # samples agreeing with a change
    _proposed: State | None = None
    _stood_before: bool = False          # was the train at rest before moving?

    def observe(self, when: float, present: bool, moving: bool) -> list:
        """Feed one sample. Returns any events that just closed."""
        wants = (State.AWAY if not present
                 else State.MOVING if moving else State.STANDING)
        if wants is self.state:
            self._run = 0
            self._proposed = None
            return []

        if wants is self._proposed:
            self._run += 1
        else:
            self._proposed, self._run = wants, 1

        # A train appearing or vanishing is believed at once; a change
        # between moving and standing has to persist.
        immediate = State.AWAY in (wants, self.state)
        if not immediate and self._run < SETTLE:
            return []
        return self._enter(wants, when)

    def _enter(self, state: State, when: float) -> list:
        closed = []
        began = self._since if self._since is not None else when
        if self.state is State.MOVING:
            if self._stood_before and state is State.STANDING:
                kind = Kind.PASSAGE      # stopped, moved, stopped again here
            elif state is State.STANDING:
                kind = Kind.ARRIVAL
            elif self._stood_before:
                kind = Kind.DEPARTURE
            else:
                kind = Kind.PASSAGE
            closed.append(Event(kind, began, when))
        elif self.state is State.STANDING:
            closed.append(Event(Kind.DWELL, began, when))

        self._stood_before = self.state is State.STANDING
        if state is State.AWAY:
            self._stood_before = False
        self.state, self._since = state, when
        self._run, self._proposed = 0, None
        self.events += closed
        return closed

    def finish(self, when: float) -> list:
        """Close whatever is open, when the camera stops watching."""
        return self._enter(State.AWAY, when) if self.state is not State.AWAY else []

    def summary(self) -> dict:
        counts = {k: 0 for k in Kind}
        for event in self.events:
            counts[event.kind] += 1
        moving = sum(e.seconds for e in self.events if e.kind is not Kind.DWELL)
        waiting = sum(e.seconds for e in self.events if e.kind is Kind.DWELL)
        return {'arrivals': counts[Kind.ARRIVAL],
                'departures': counts[Kind.DEPARTURE],
                'passages': counts[Kind.PASSAGE],
                'moving_s': moving, 'dwell_s': waiting}
