"""Tests for following each train separately.

An episode used to carry one path however many trains were in view, so
two trains crossing became one record with one entry time, one exit time
and one direction. On 30/8 seven episodes held two trains, and two ran
for 17 and 29 minutes because a standing rake kept the episode alive
while others passed through it.
"""

from tracking import Detection, TrainTracker


def moving(x: int, y: int, size: int = 60, conf: float = 0.9) -> Detection:
    return Detection(box=(x, y, x + size, y + size), conf=conf,
                     centre=(x + size // 2, y + size // 2))


class TestSeparatingTrains:
    def test_two_trains_become_two_tracks(self):
        tracker = TrainTracker()
        for step in range(8):
            tracker.update(float(step), [
                moving(100 + step * 20, 100),      # running through
                moving(600, 300),                  # standing in the loop
            ])
        assert len(tracker.substantial()) == 2

    def test_a_single_train_stays_one_track(self):
        tracker = TrainTracker()
        for step in range(8):
            tracker.update(float(step), [moving(100 + step * 20, 100)])
        assert len(tracker.substantial()) == 1

    def test_a_track_records_where_it_went(self):
        tracker = TrainTracker()
        for step in range(8):
            tracker.update(float(step), [moving(100 + step * 25, 100)])
        track = tracker.substantial()[0]
        assert len(track.path) >= 6
        assert track.path[-1][1] > track.path[0][1], 'travelled to the right'

    def test_something_that_never_moves_still_tracks(self):
        """The roof at Williton 2 held still for 130 sightings.

        It must be followed like anything else — what marks it out is the
        path going nowhere, which is only visible once it has one.
        """
        tracker = TrainTracker()
        for step in range(10):
            tracker.update(float(step), [moving(174, 316)])
        track = tracker.substantial()[0]
        assert track.path[0][1:] == track.path[-1][1:]

    def test_empty_frames_are_still_passed_on(self):
        """Lost tracks age on every update, including quiet ones.

        Skipping empty frames would keep a departed train alive forever
        and let the next one inherit its identity.
        """
        tracker = TrainTracker()
        for step in range(5):
            tracker.update(float(step), [moving(100, 100)])
        before = len(tracker.tracks)
        for step in range(5, 60):
            tracker.update(float(step), [])
        assert len(tracker.tracks) == before, 'no new tracks from empty frames'

    def test_reset_forgets_everything(self):
        tracker = TrainTracker()
        for step in range(5):
            tracker.update(float(step), [moving(100 + step * 20, 100)])
        assert tracker.tracks
        tracker.reset()
        assert not tracker.tracks
