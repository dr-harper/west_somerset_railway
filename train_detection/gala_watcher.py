"""Two-tier train watcher for the WSR live webcams.

Tier 1 (always on, ~2 Hz, near-zero compute): each camera keeps its HLS
stream open and runs a zone-masked motion gate — downscaled greyscale
frame differencing against a running-average background. Parked stock is
absorbed by the background and never fires the gate.

Tier 2 (only while the gate is open): YOLO confirms a train in a
detect/approach zone, then tracks it at ~1 Hz until it leaves. Each
passage is logged as one episode with enter/exit times, zone history,
centroid drift (=> direction), keyframes, and a low-fps clip.

Designed to ramp down to small compute: the idle cost is six 480p decodes
plus thumbnail maths; inference only runs while something is moving.

Usage:
    python3 gala_watcher.py --hours 11          # e.g. 08:00 -> 19:00
    python3 gala_watcher.py --hours 0.5 --dry-run   # gate test, no YOLO
"""

import argparse
import json
import math
import queue
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from detection_zones import ZONES, classify
from track_geometry import (corridor_mask, direction_of_motion, exclusion_mask,
                            minehead_end_known, project, regions_of)
from live_snapshots import write_snapshot
from wsr_live_capture import CAMERAS, BotChallenge, resolve_hls_url


def grab_hires_still(camera: str, out_path: Path, delay_s: float = 4.0) -> None:
    """Best-effort 1080p still for classification crops (runs in its own
    thread; the continuous pipeline stays at 480p). Waits a short beat so
    approach-zone episodes have the train close to camera rather than a
    speck in the distance, but not so long that only coaches remain: at
    line speed every second of delay is another 11 m of train past the
    lens, and 12s put the locomotive 134 m gone."""
    try:
        time.sleep(delay_s)
        url = resolve_hls_url(camera, format_spec='270/232/231')
        cap = cv2.VideoCapture(url)
        ok, frame = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(str(out_path), frame)
    except Exception:
        pass

HERE = Path(__file__).parent
EPISODES_PATH = HERE / 'episodes.jsonl'
GATE_LOG_PATH = HERE / 'gate_log.jsonl'
CAPTURE_DIR = HERE / 'captures'

# Processing geometry: motion runs at half stream resolution
STREAM_W, STREAM_H = 854, 480
PROC_W, PROC_H = 427, 240
SCALE = PROC_W / STREAM_W

MOTION_SAMPLE_S = 0.5          # tier-1 cadence
YOLO_SAMPLE_S = 1.0            # tier-2 cadence while an episode is active
MOTION_THRESHOLD = 25          # per-pixel absdiff threshold (0-255)
MOTION_FRACTION = 0.02         # fraction of zone mask that must change
MOTION_CONSECUTIVE = 3         # samples needed to open the gate
GLOBAL_JUMP_FRACTION = 0.35    # whole-frame change => exposure/camera jump
CANDIDATE_TIMEOUT_S = 6        # YOLO tries before a gate is called false
# Motion is logged as a coarse grid of cells rather than a single number,
# so a run's false gates can afterwards be turned into an exclusion map:
# cells that move often but never yield a train are what to mask.
MOTION_GRID_W, MOTION_GRID_H = 16, 9

CHALLENGE_BACKOFF_S = 900      # wait this long after a bot challenge
BACKFILL_STEP_S = 1.0          # how coarsely to rewind through the buffer
BACKFILL_CONF = 0.35           # a train entering frame scores lower than one
                               # filling it, so accept less when rewinding
EPISODE_GONE_S = 10            # no train for this long closes the episode
BACKGROUND_ALPHA = 0.05        # background adaption rate when idle
URL_REFRESH_S = 4 * 3600       # HLS URLs expire after ~6h; refresh early
CLIP_FPS = 2
# H.264, not the 'mp4v' MPEG-4 Part 2 OpenCV defaults to: browsers cannot
# decode the latter, so the clips played nowhere but a desktop player.
CLIP_FOURCC = 'avc1'
# While a train is actually in view, keep every frame the decoder hands
# us. Sampling at 2Hz sounds dense but works out at roughly one frame
# every five seconds of real time once inference and stream reads are
# accounted for, and a train at 20mph covers 45m in that gap — too far
# apart for optical flow to find a match or for two frames to share any
# overlap. At stream rate the same train moves 0.36m a frame, which is
# what following motion and stitching a train together both need.
DENSE_FPS = 25
DENSE_MAX_FRAMES = 500          # 20s, enough for any single passage

# Dense recording starts when the gate confirms a train, by which time the
# locomotive has often already gone through: episode 164144_watchet_1 was
# noticed at 16:41:54 and backfilled ten seconds, so its dense clip opens
# on the coaches. A rolling pre-roll fixes that the way a high-speed
# camera does — always recording, only ever keeping the recent past.
#
# Held as JPEG rather than raw frames: eight seconds of raw 854x480 is
# 150MB a camera and there are eleven of them, where encoded it is nearer
# 6MB. Ten a second is well short of the stream's 25 but is five times what
# the gate samples at, and enough to catch a locomotive entering frame.
PREROLL_FPS = 10
PREROLL_SECONDS = 25
SNAPSHOT_EVERY_S = 60          # recent still per camera, for the control room

# Image-space unit vector meaning "travelling northbound (towards Minehead)".
# Validated 29/8 against timetable-confirmed movements: Bishops Lydeard,
# Blue Anchor, Crowcombe and Minehead all agree; Seaward Crossing is still
# unvalidated for want of a decisive sighting.
NORTHBOUND_VECTORS = {
    'minehead_station': (0.0, 1.0),            # arriving = towards camera
    'minehead_seaward_crossing': (-0.95, 0.3), # sign-checked v the 08:10 ex-Minehead 29/8: departing (SB) drifts right
    'blue_anchor': (0.0, -1.0),                # away, towards Dunster
    'watchet_visitor_centre': (0.0, 0.0),      # see UNRELIABLE_DRIFT_CAMERAS
    'crowcombe_heathfield': (-0.9, -0.45),     # away, towards Stogumber
    'bishops_lydeard': (0.4, -0.9),            # departing, towards the yard
}


# Cameras looking along a curve give drift that does not separate the two
# directions: at Watchet on 29/8 northbound trains drifted strongly left
# while southbound ones drifted strongly down, so no single vector fits.
# Direction for these comes from the order of stations a movement visits.
# Bishops Lydeard joins Watchet on the evidence of audit_directions.py,
# which checks labels against the locomotive the classifier read and the
# working the timetable gives it — evidence owing nothing to drift. Both
# checkable sightings there were labelled backwards, and two nearly
# parallel drifts, (-311,+140) and (-349,+243), belong to workings in
# opposite directions. No single vector separates those, so drift at this
# camera cannot decide direction and the movement's station order must.
UNRELIABLE_DRIFT_CAMERAS = {'watchet_visitor_centre', 'bishops_lydeard'}


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def stamp() -> str:
    return datetime.now().strftime('%Y%m%dT%H%M%S')


class SharedDetector:
    """One YOLO instance shared by all camera threads."""

    def __init__(self, weights: str):
        from ultralytics import YOLO
        import torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.model = YOLO(weights)
        self.lock = threading.Lock()

    def trains(self, frame, conf=0.4):
        """Return [(conf, (x1,y1,x2,y2), (cx,cy), zone, kind), ...]."""
        with self.lock:
            results = self.model(frame, verbose=False, conf=conf,
                                 device=self.device)[0]
        names = self.model.names
        out = []
        for box in results.boxes:
            if names[int(box.cls)] != 'train':
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            out.append((round(float(box.conf), 3), (x1, y1, x2, y2), (cx, cy)))
        return out


class CameraWorker(threading.Thread):
    def __init__(self, camera: str, detector, log_queue, dry_run: bool):
        super().__init__(daemon=True, name=camera)
        self.camera = camera
        self.detector = detector
        self.log_queue = log_queue
        self.dry_run = dry_run
        self.mask = self._build_mask()
        # The block-out has two jobs and they need different rules. For the
        # motion gate it applies wholesale: a level crossing is painted out
        # precisely because people walk over it, and none of that should
        # open a gate.
        #
        # For rejecting detections it cannot apply wholesale, because a
        # train crossing that same spot is still a train. Geometry will not
        # separate them either — the roof that produced 95 of Williton 2's
        # detections sits 0.83 gauges from the traced loop, closer than
        # some of the track itself. What separates them is that the roof
        # never moves. So inside painted areas a detection counts only if
        # something actually changed there.
        self.blocked_mask = exclusion_mask(self.camera, PROC_W, PROC_H)
        self.last_changed = None
        self.background = None
        self.cap = None
        self.url_time = 0.0
        self.consecutive_motion = 0
        self.state = 'IDLE'            # IDLE | CANDIDATE | ACTIVE
        self.state_since = time.time()
        self.last_train_time = 0.0
        self.episode = None
        self.frame_buffer = []         # (t, frame) rolling ~30s at 2 Hz
        # (t, jpeg) at PREROLL_FPS, so an episode can begin before it was noticed
        self.preroll: deque = deque(maxlen=PREROLL_FPS * PREROLL_SECONDS)
        self.last_preroll = 0.0
        self.heartbeat = time.time()
        self.last_motion_cells: list[int] = []
        self.last_snapshot = 0.0
        self.dense_writer = None
        self.dense_path = None
        self.dense_count = 0
        self.stats = {'gates': 0, 'false_gates': 0, 'episodes': 0,
                      'reconnects': 0, 'jumps': 0, 'challenges': 0}

    # --- setup -----------------------------------------------------------

    def _build_mask(self):
        """Where the motion gate is allowed to look.

        Detect and approach zones minus any annotated exclusions. On 29/8
        95% of gate openings were false — crowds on platforms, traffic at
        the Blue Anchor crossing, flowerbeds in the wind — and each one
        cost up to six YOLO calls. Subtracting those areas is the single
        cheapest accuracy and compute win available.
        """
        mask = np.zeros((PROC_H, PROC_W), np.uint8)
        for _name, kind, poly in ZONES.get(self.camera, []):
            if kind in ('detect', 'approach'):
                pts = (np.array(poly, np.float32) * SCALE).astype(np.int32)
                cv2.fillPoly(mask, [pts], 255)
        if not mask.any():
            # No hand-drawn zones. Without this the mask is empty, the gate
            # never opens, and the camera is silently blind rather than
            # noisily broken — so fall back to the traced rails.
            mask = corridor_mask(self.camera, PROC_W, PROC_H)
        blocked = exclusion_mask(self.camera, PROC_W, PROC_H)
        before = int((mask > 0).sum())
        mask[blocked > 0] = 0
        after = int((mask > 0).sum())
        if before and after < before:
            self.log_queue.put(('info', {
                'ts': now_iso(), 'camera': self.camera,
                'message': f'motion mask reduced {before} -> {after} px '
                           f'({100 * (before - after) // before}% blocked)'}))
        return mask

    def _connect(self):
        if self.cap is not None:
            self.cap.release()
        url = resolve_hls_url(self.camera)
        self.cap = cv2.VideoCapture(url)
        self.url_time = time.time()
        self.background = None
        self.consecutive_motion = 0

    # --- tier 1: motion gate --------------------------------------------

    def _motion_fraction(self, frame) -> tuple[float, float]:
        small = cv2.resize(frame, (PROC_W, PROC_H))
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        grey = cv2.GaussianBlur(grey, (5, 5), 0)
        if self.background is None:
            self.background = grey.copy()
            return 0.0, 0.0
        diff = cv2.absdiff(grey, self.background)
        changed = (diff > MOTION_THRESHOLD).astype(np.uint8)
        global_frac = float(changed.mean())
        zone_frac = float(changed[self.mask > 0].mean()) if self.mask.any() else 0.0
        self.last_motion_cells = self._motion_cells(changed)
        self.last_changed = changed
        # adapt the background only while idle so a dwelling train
        # is not absorbed mid-episode
        if self.state == 'IDLE':
            cv2.accumulateWeighted(grey, self.background, BACKGROUND_ALPHA)
        return zone_frac, global_frac

    def _motion_cells(self, changed) -> list[int]:
        """Which cells of a coarse grid moved, as flat indices.

        Compact enough to log on every gate, specific enough to build a
        heat map from afterwards.
        """
        cell_h = changed.shape[0] // MOTION_GRID_H
        cell_w = changed.shape[1] // MOTION_GRID_W
        if cell_h == 0 or cell_w == 0:
            return []
        cells = []
        for row in range(MOTION_GRID_H):
            for col in range(MOTION_GRID_W):
                block = changed[row * cell_h:(row + 1) * cell_h,
                                col * cell_w:(col + 1) * cell_w]
                if block.mean() > 0.05:
                    cells.append(row * MOTION_GRID_W + col)
        return cells

    # --- tier 2: episodes ------------------------------------------------

    def _backfill_entry(self, trigger_time):
        """Rewind to the frame where the train first appeared.

        The gate needs 1.5s of sustained motion and YOLO then runs once a
        second, so by the time an episode opens the locomotive is often
        already through the frame. Walking back recovers an honest entry
        time, which is what delay is measured from, and a still showing
        the front of the train rather than its coaches.

        This reads the pre-roll rather than the 2Hz frame buffer. That
        buffer held twelve seconds, and on 30/8 one hundred and forty-four
        of one hundred and eighty-nine backfills came back at exactly ten
        seconds — they were hitting the end of it, not finding the train.
        Every one of those entry times was a floor, and since a floor that
        is too late makes a train look later than it ran, every delay
        measured from them was overstated. The pre-roll reaches
        PREROLL_SECONDS back at PREROLL_FPS, so the search now ends when
        the train genuinely is not there.
        """
        earlier = [(when, encoded) for when, encoded in list(self.preroll)
                   if when < trigger_time]
        if not earlier:
            return None
        earliest = None
        checked = trigger_time
        for when, encoded in sorted(earlier, key=lambda item: item[0],
                                    reverse=True):
            if checked - when < BACKFILL_STEP_S:
                continue
            checked = when
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if not self._detect(frame, conf=BACKFILL_CONF):
                break      # train not yet in view: we have gone back far enough
            earliest = (when, frame)
        return earliest

    def _start_episode(self, t, detections, frame):
        self.stats['episodes'] += 1
        entry = self._backfill_entry(t)
        entry_offset = round(t - entry[0], 1) if entry else 0.0
        self.episode = {
            'camera': self.camera,
            't_enter': now_iso(),
            'zones': [],
            'centroids': [],
            'peak_conf': 0.0,
            'keyframes': [],
            'most_in_frame': 0,
            'clip_frames': [f for (ft, f) in self.frame_buffer if t - ft <= 6],
            'entry_backfilled_s': entry_offset,
        }
        # Stream-rate frames go straight to disk rather than into memory:
        # 500 raw frames is 600MB per camera, and several cameras can be
        # in an episode at once.
        dense_path = CAPTURE_DIR / f'{stamp()}_{self.camera}_dense.mp4'
        self.dense_writer = cv2.VideoWriter(
            str(dense_path), cv2.VideoWriter_fourcc(*'avc1'),
            DENSE_FPS, (STREAM_W, STREAM_H))
        self.dense_path = dense_path
        self.dense_count = 0
        # Everything from just before the train was noticed, so the clip
        # opens on the locomotive arriving rather than on its coaches.
        # Each pre-roll frame is held for its real duration: it was
        # sampled at PREROLL_FPS and the file is written at DENSE_FPS, so
        # writing them one-for-one would play those seconds two and a half
        # times too fast and make any timing taken from the clip wrong.
        hold = DENSE_FPS / PREROLL_FPS
        owed = 0.0
        for when, encoded in list(self.preroll):
            if t - when > PREROLL_SECONDS:
                continue
            earlier = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if earlier is None:
                continue
            owed += hold
            while owed >= 1:
                self.dense_writer.write(earlier)
                self.dense_count += 1
                owed -= 1
        self.episode_preroll_frames = self.dense_count

        if entry:
            # the frame where the train first appeared, not where we noticed
            path = CAPTURE_DIR / f'{stamp()}_{self.camera}_entry.jpg'
            cv2.imwrite(str(path), entry[1])          # clean, as above
            self.episode['entry_frame'] = path.name
        hires_path = CAPTURE_DIR / f'{stamp()}_{self.camera}_hires.jpg'
        self.episode['hires'] = hires_path.name
        threading.Thread(target=grab_hires_still,
                         args=(self.camera, hires_path), daemon=True).start()
        self._observe(t, detections, frame, keyframe=True)

    def _observe(self, t, detections, frame, keyframe=False):
        ep = self.episode
        # Follow one train, not whichever is most confident this second.
        # A scene can hold two — Williton is a crossing place and had a
        # train on each road five times on 30/8 — and taking the highest
        # score each time makes the tracked point teleport between them:
        # jumps of 300 to 557 px against a typical step of one or two. The
        # drift computed from that is meaningless, and at Bishops Lydeard
        # it produced a confident 'northbound' out of nothing.
        previous = ep['centroids'][-1][1] if ep['centroids'] else None
        if previous is None:
            best = max(detections, key=lambda d: d['conf'])
        else:
            best = min(detections,
                       key=lambda d: math.dist(d['centre'], previous))
        ep['centroids'].append((t, best['centre']))
        ep['most_in_frame'] = max(ep.get('most_in_frame', 0), len(detections))
        for d in detections:
            if d['zone'] and d['zone'] not in ep['zones']:
                ep['zones'].append(d['zone'])
        if best['conf'] > ep['peak_conf'] + 0.1 or keyframe:
            ep['peak_conf'] = max(ep['peak_conf'], best['conf'])
            # The still is written clean and the boxes recorded beside it.
            # Burning the overlay into the pixels made it permanent: it
            # could not be turned off to read a running number underneath,
            # and it was baked into the only copy, so a later classifier
            # saw the annotation as part of the photograph.
            path = CAPTURE_DIR / f'{stamp()}_{self.camera}_key.jpg'
            cv2.imwrite(str(path), frame)
            ep['keyframes'].append(path.name)
            height, width = frame.shape[:2]
            ep.setdefault('boxes', {})[path.name] = {
                'width': width,
                'height': height,
                'detections': [
                    {'box': list(d['box']), 'conf': d['conf'], 'zone': d['zone']}
                    for d in detections
                ],
            }
        ep['peak_conf'] = max(ep['peak_conf'], best['conf'])
        if len(ep['clip_frames']) < 300:   # cap clip memory on long dwells
            ep['clip_frames'].append(frame)

    def _close_episode(self):
        ep = self.episode
        self.episode = None
        centroids = ep.pop('centroids')
        # Persist where the train actually was, not just its net drift:
        # track geometry needs a position to take the local tangent at,
        # which a single drift vector cannot supply (29/8 lesson).
        ep['path'] = [[round(t - centroids[0][0], 1), c[0], c[1]]
                      for t, c in centroids]
        clip_frames = ep.pop('clip_frames')
        ep['t_exit'] = now_iso()
        offset = ep.pop('entry_backfilled_s', 0.0)
        if offset:
            entered = datetime.fromisoformat(ep['t_enter'])
            ep['t_noticed'] = ep['t_enter']
            ep['t_enter'] = (entered - timedelta(seconds=offset)).isoformat(
                timespec='seconds')
            ep['entry_backfilled_s'] = offset
        ep['n_observations'] = len(centroids)
        # Nearest-neighbour keeps the track on one train while both are in
        # view, but not when the followed train leaves and the other is
        # picked up. A remaining jump means the path is two trains stitched
        # together, and nothing measured along it can be trusted.
        steps = [math.dist(a[1], b[1]) for a, b in zip(centroids, centroids[1:])]
        if steps:
            typical = sorted(steps)[len(steps) // 2]
            ep['path_jumps'] = sum(
                1 for s in steps if s > max(60.0, typical * 6))
        if len(centroids) >= 2:
            (t0, (x0, y0)), (t1, (x1, y1)) = centroids[0], centroids[-1]
            drift = (x1 - x0, y1 - y0)
            ep['drift_px'] = drift
            # Prefer the traced rails: their local tangent follows a real
            # train's drift far more closely than a hand-estimated vector
            # (mean margin 0.93 against 0.76 over the 29/8 episodes, and
            # 1.00 against 0.44 at Blue Anchor). The hand vector remains
            # the authority on sign, so the tangent is only trusted where
            # the trace's Minehead end has been established.
            magnitude = (drift[0] ** 2 + drift[1] ** 2) ** 0.5
            nvec = NORTHBOUND_VECTORS.get(self.camera)
            if (ep.get('path_jumps') or self.camera in UNRELIABLE_DRIFT_CAMERAS
                    or magnitude < 30):
                # A confidently wrong direction is worse than none: it
                # stops the sighting chaining, because a candidate whose
                # direction contradicts the heading is rejected outright.
                ep['direction'] = 'unclear'
            elif minehead_end_known(self.camera):
                ep['direction'] = direction_of_motion(
                    self.camera, centroids[-1][1], drift)
            elif nvec:
                dot = drift[0] * nvec[0] + drift[1] * nvec[1]
                ep['direction'] = 'northbound' if dot > 0 else 'southbound'
            else:
                # Axis known, sign not. A confidently reversed direction is
                # worse than none; chaining recovers it from station order.
                ep['direction'] = 'unclear'
        else:
            ep['direction'] = 'unclear'
        # low-fps clip for review / future training data
        if clip_frames:
            path = CAPTURE_DIR / f"{stamp()}_{self.camera}_clip.mp4"
            writer = cv2.VideoWriter(str(path),
                                     cv2.VideoWriter_fourcc(*'avc1'),
                                     CLIP_FPS, (STREAM_W, STREAM_H))
            for f in clip_frames:
                writer.write(f)
            writer.release()
            ep['clip'] = path.name

        # The dense clip is what motion work reads: written at the rate it
        # was sampled, so timings taken from it are real.
        if self.dense_writer is not None:
            self.dense_writer.release()
            self.dense_writer = None
            if self.dense_count >= 10:
                ep['dense_clip'] = self.dense_path.name
                ep['dense_frames_kept'] = self.dense_count
                ep['dense_preroll_frames'] = getattr(
                    self, 'episode_preroll_frames', 0)
            elif self.dense_path.exists():
                self.dense_path.unlink()      # too short to be worth keeping
        self.log_queue.put(('episode', ep))

    # --- main loop -------------------------------------------------------

    def run(self):
        backoff = 2
        last_motion_check = 0.0
        last_yolo = 0.0
        gate_cells: list[int] = []
        while True:
            try:
                if self.cap is None or time.time() - self.url_time > URL_REFRESH_S:
                    self._connect()
                    backoff = 2
                grabbed = self.cap.grab()
                if not grabbed:
                    raise RuntimeError('stream read failed')
                self.heartbeat = time.time()
                t = time.time()
                # Decode every frame while an episode is running, and only
                # every MOTION_SAMPLE_S otherwise. The frames are already
                # being grabbed either way; this only decides whether they
                # are decoded and kept.
                dense = (self.state == 'ACTIVE' and self.episode is not None
                         and self.dense_writer is not None
                         and self.dense_count < DENSE_MAX_FRAMES)
                due = t - last_motion_check >= MOTION_SAMPLE_S
                preroll_due = t - self.last_preroll >= 1.0 / PREROLL_FPS
                if not due and not dense and not preroll_due:
                    continue
                ok, frame = self.cap.retrieve()
                if not ok:
                    raise RuntimeError('retrieve failed')
                if dense:
                    self.dense_writer.write(frame)
                    self.dense_count += 1
                elif preroll_due:
                    # Only while no episode is running: once one is, the
                    # frames are going to the clip anyway.
                    self.last_preroll = t
                    ok, encoded = cv2.imencode(
                        '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ok:
                        self.preroll.append((t, encoded))
                if not due:
                    continue
                last_motion_check = t

                self.frame_buffer.append((t, frame))
                # A recent still per camera for the control room. The frame
                # is already decoded, so this costs a JPEG encode a minute
                # and saves opening the stream again from elsewhere.
                if t - self.last_snapshot > SNAPSHOT_EVERY_S:
                    self.last_snapshot = t
                    write_snapshot(self.camera, frame)
                self.frame_buffer = [(ft, f) for ft, f in self.frame_buffer
                                     if t - ft <= 12]

                zone_frac, global_frac = self._motion_fraction(frame)
                if global_frac > GLOBAL_JUMP_FRACTION:
                    # exposure change or camera jump: rebuild background
                    self.stats['jumps'] += 1
                    self.background = None
                    continue

                moving = zone_frac > MOTION_FRACTION
                self.consecutive_motion = self.consecutive_motion + 1 if moving else 0

                if self.state == 'IDLE':
                    if self.consecutive_motion >= MOTION_CONSECUTIVE:
                        self.stats['gates'] += 1
                        self.log_queue.put(('gate', {
                            'ts': now_iso(), 'camera': self.camera,
                            'zone_fraction': round(zone_frac, 4),
                            'cells': self.last_motion_cells}))
                        if self.dry_run:
                            self.consecutive_motion = 0
                        else:
                            gate_cells = list(self.last_motion_cells)
                            self.state, self.state_since = 'CANDIDATE', t
                elif self.state == 'CANDIDATE':
                    if t - last_yolo >= YOLO_SAMPLE_S:
                        last_yolo = t
                        detections = self._detect(frame)
                        if detections:
                            self.state, self.state_since = 'ACTIVE', t
                            self.last_train_time = t
                            self._start_episode(t, detections, frame)
                        elif t - self.state_since > CANDIDATE_TIMEOUT_S:
                            self.stats['false_gates'] += 1
                            self.log_queue.put(('false_gate', {
                                'ts': now_iso(), 'camera': self.camera,
                                'cells': gate_cells}))
                            self.state = 'IDLE'
                elif self.state == 'ACTIVE':
                    if t - last_yolo >= YOLO_SAMPLE_S:
                        last_yolo = t
                        detections = self._detect(frame)
                        if detections:
                            self.last_train_time = t
                            self._observe(t, detections, frame)
                        elif t - self.last_train_time > EPISODE_GONE_S:
                            self._close_episode()
                            self.state = 'IDLE'
            except Exception as exc:
                challenged = isinstance(exc, BotChallenge)
                self.log_queue.put(('error', {
                    'ts': now_iso(), 'camera': self.camera,
                    'challenge': challenged, 'error': str(exc)[:200]}))
                self.stats['reconnects'] += 1
                if challenged:
                    self.stats['challenges'] += 1
                if self.episode:
                    self._close_episode()
                self.state = 'IDLE'
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                # A challenge is a rate limit, not a blip: retrying promptly
                # deepens it. On 29/8 six cameras retried into one for half an
                # hour and stayed blind throughout.
                time.sleep(CHALLENGE_BACKOFF_S if challenged else backoff)
                backoff = min(backoff * 2, 120)

    def _moved_within(self, box) -> bool:
        """Whether anything changed inside a detection box.

        The test that tells a train crossing a painted level crossing from
        the static structure the paint was aimed at. Without the motion
        record — the very first frames, or a background still building —
        the benefit of the doubt goes to the train.
        """
        changed = self.last_changed
        if changed is None:
            return True
        x1, y1, x2, y2 = (int(v * SCALE) for v in box)
        x1 = max(0, min(changed.shape[1] - 1, x1))
        x2 = max(x1 + 1, min(changed.shape[1], x2))
        y1 = max(0, min(changed.shape[0] - 1, y1))
        y2 = max(y1 + 1, min(changed.shape[0], y2))
        return bool(changed[y1:y2, x1:x2].mean() > MOTION_FRACTION)

    def _detect(self, frame, conf: float = 0.5):
        detections = []
        zones = ZONES.get(self.camera)
        # The block-out gated motion but not detections, so a static
        # structure inside a zone kept producing trains: the roof in the
        # foreground at Williton 2 accounted for 95 of that camera's 111
        # detections on 30/8, at up to 0.82 confidence, and projected onto
        # the loop at 0.83 gauges — close enough that geometry alone can
        # never reject it.
        blocked = self.blocked_mask
        for confidence, box, centre in self.detector.trains(frame):
            if confidence < conf:
                continue
            if blocked is not None:
                cx = min(blocked.shape[1] - 1, max(0, int(centre[0] * SCALE)))
                cy = min(blocked.shape[0] - 1, max(0, int(centre[1] * SCALE)))
                if blocked[cy, cx] > 0 and not self._moved_within(box):
                    continue
            if zones:
                zone = classify(self.camera, centre)
                kind = next((k for n, k, _ in zones if n == zone), None)
                accepted = kind in ('detect', 'approach')
            else:
                # Newer cameras have traced rails but no hand-drawn zones.
                # The rails say the same thing more precisely: a detection
                # belongs if it sits on a road.
                placed = project(self.camera, centre)
                accepted = bool(placed and placed['on_track'])
                zone = placed['track'] if placed else None
            if accepted:
                detections.append({'conf': confidence, 'box': box,
                                   'centre': centre, 'zone': zone})
        return detections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=11.0)
    parser.add_argument('--dry-run', action='store_true',
                        help='motion gate only: log gates, never run YOLO')
    args = parser.parse_args()

    CAPTURE_DIR.mkdir(exist_ok=True)
    detector = None if args.dry_run else SharedDetector(str(HERE / 'yolo11s.pt'))
    log_queue: queue.Queue = queue.Queue()
    workers = [CameraWorker(cam, detector, log_queue, args.dry_run)
               for cam in CAMERAS]
    for w in workers:
        w.start()

    deadline = time.time() + args.hours * 3600
    last_report = time.time()
    episode_count = 0
    while time.time() < deadline:
        try:
            kind, payload = log_queue.get(timeout=5)
        except queue.Empty:
            kind = None
        if kind == 'episode':
            episode_count += 1
            with EPISODES_PATH.open('a') as fh:
                fh.write(json.dumps(payload) + '\n')
            print(f"EPISODE {payload['camera']} {payload['t_enter']} -> "
                  f"{payload['t_exit']} {payload.get('direction')} "
                  f"zones={payload['zones']} peak={payload['peak_conf']}",
                  flush=True)
        elif kind in ('gate', 'false_gate', 'error', 'info'):
            with GATE_LOG_PATH.open('a') as fh:
                fh.write(json.dumps({'kind': kind, **payload}) + '\n')
        if time.time() - last_report > 600:
            last_report = time.time()
            summary = {w.camera: dict(w.stats,
                                      state=w.state,
                                      stale=round(time.time() - w.heartbeat))
                       for w in workers}
            print(f'--- {datetime.now():%H:%M:%S} status: '
                  + json.dumps(summary), flush=True)

    print(f'watcher finished: {episode_count} episodes')


if __name__ == '__main__':
    main()
