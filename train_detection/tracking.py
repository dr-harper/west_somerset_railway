"""Follow each train separately, so one camera can watch two at once.

An episode used to be "something is visible at this camera", carrying a
single path. That collapses two trains into one record: on 30/8 seven
episodes held two trains, and two of them ran for 17 and 29 minutes
because a standing rake kept the episode alive while other trains passed
through it. One entry time, one exit time and one direction for all of
that.

Tracking is a solved problem and this uses the solution rather than a
private one: ByteTrack, as shipped with ultralytics, one tracker per
camera. It is fed the boxes our shared detector already produces, so the
detector stays shared and only the association state is per-camera.

What comes back is a track id that persists across frames, which turns a
camera visit into a set of trains, each with its own path, its own entry
and exit, and its own direction.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TrackerSettings:
    """ByteTrack's knobs, named here so the choices are visible.

    The defaults are tuned for crowded video at 30fps. Trains are sampled
    about once a second, move slowly and rarely overlap, so association
    can afford to be looser in time and stricter about starting a new
    track — a spurious second track would put a train on the line twice.
    """

    tracker_type: str = 'bytetrack'
    track_high_thresh: float = 0.4
    track_low_thresh: float = 0.15
    new_track_thresh: float = 0.5
    # A train can sit behind a footbridge or a signal box for several
    # samples; at roughly 1Hz, 30 frames is half a minute of patience.
    track_buffer: int = 30
    match_thresh: float = 0.75
    fuse_score: bool = True


@dataclass
class Detection:
    box: tuple[int, int, int, int]
    conf: float
    centre: tuple[int, int]
    zone: str | None = None


@dataclass
class Track:
    """One train, followed across the frames it was visible in."""

    track_id: int
    first_seen: float
    last_seen: float
    path: list = field(default_factory=list)     # (t, x, y)
    peak_conf: float = 0.0
    zones: list = field(default_factory=list)

    def observe(self, when: float, detection: Detection) -> None:
        self.last_seen = when
        self.path.append((when, detection.centre[0], detection.centre[1]))
        self.peak_conf = max(self.peak_conf, detection.conf)
        if detection.zone and detection.zone not in self.zones:
            self.zones.append(detection.zone)


class _Results:
    """The shape ByteTrack expects, without a YOLO Results object.

    It reads .xywh, .conf and .cls off what it is handed and splits that
    by boolean mask into high and low confidence sets, so the holder has
    to support indexing as well as attribute access. Keeping this small
    is what lets the detector stay shared between cameras while only the
    association state is per-camera.
    """

    def __init__(self, xywh: np.ndarray, conf: np.ndarray, cls: np.ndarray):
        self.xywh = xywh
        self.conf = conf
        self.cls = cls

    @classmethod
    def of(cls, detections: list[Detection]) -> '_Results':
        boxes = []
        for detection in detections:
            x1, y1, x2, y2 = detection.box
            boxes.append([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1])
        return cls(
            np.array(boxes, dtype=np.float32).reshape(-1, 4),
            np.array([d.conf for d in detections], dtype=np.float32),
            np.zeros(len(detections), dtype=np.float32),
        )

    def __getitem__(self, mask) -> '_Results':
        return _Results(self.xywh[mask], self.conf[mask], self.cls[mask])

    def __len__(self) -> int:
        return len(self.conf)


class TrainTracker:
    """Per-camera association of detections into trains."""

    def __init__(self, settings: TrackerSettings | None = None):
        from ultralytics.trackers import BYTETracker

        self.settings = settings or TrackerSettings()
        self._tracker = BYTETracker(self.settings)
        self.tracks: dict[int, Track] = {}

    def update(self, when: float, detections: list[Detection]) -> list[Track]:
        """Associate this frame's detections, returning the tracks seen now.

        An empty frame is still passed on: ByteTrack ages its lost tracks
        on every update, and skipping the quiet frames would keep a
        departed train alive indefinitely.
        """
        rows = self._tracker.update(_Results.of(detections))
        seen = []
        for row in rows:
            # rows are [x1, y1, x2, y2, track_id, conf, cls, detection_index]
            track_id = int(row[4])
            index = int(row[-1]) if len(row) > 7 else None
            if index is None or index >= len(detections):
                continue
            detection = detections[index]
            track = self.tracks.get(track_id)
            if track is None:
                track = Track(track_id=track_id, first_seen=when, last_seen=when)
                self.tracks[track_id] = track
            track.observe(when, detection)
            seen.append(track)
        return seen

    def reset(self) -> None:
        from ultralytics.trackers import BYTETracker

        self._tracker = BYTETracker(self.settings)
        self.tracks = {}

    def substantial(self, min_observations: int = 2) -> list[Track]:
        """Tracks with enough sightings to say anything about."""
        return [t for t in self.tracks.values()
                if len(t.path) >= min_observations]
