import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Redo2, Save, Trash2, Undo2 } from 'lucide-react';
import { CAMERAS } from '../../services/cameras';
import {
  countPoints, FRAME_HEIGHT, FRAME_WIDTH, isReady, loadTraces, saveTraces,
  type CameraTrace, type Point, type TraceFile,
} from '../../services/cameraTracks';
import styles from './AdminAnnotate.module.css';
import admin from './Admin.module.css';

/**
 * Tracing what each camera is looking at, inside the control room.
 *
 * This was a separate page on a separate server on a separate port, which
 * meant a second thing to start, a second thing to notice had stopped, and
 * a cameras screen that could report a camera as un-traced without offering
 * any way to trace it. The health panel now sends an operator here, and
 * here can actually fix it.
 *
 * Everything is drawn in the 854x480 space the watcher works in, whatever
 * size the picture is on screen, so a trace made on a phone means the same
 * thing as one made at a desk.
 */

type Mode = 'rails' | 'regions' | 'mask';

const RAIL_COLOURS = { a: '#ffd34d', b: '#7fd1ff' };
const REGION_COLOURS = { platform: '#79e3a5', occluder: '#ff8f7a' };

export const AdminAnnotate: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const [traces, setTraces] = useState<TraceFile>({});
  // Arriving from a camera, or from the alert that named one, should open
  // that camera rather than whichever happens to be first.
  const [camera, setCamera] = useState(
    () => params.get('camera') ?? CAMERAS[0]?.id ?? '');
  const [mode, setMode] = useState<Mode>('rails');
  const [rail, setRail] = useState<'a' | 'b'>('a');
  const [roadIndex, setRoadIndex] = useState(0);
  const [regionIndex, setRegionIndex] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frameOk, setFrameOk] = useState(true);
  const [undone, setUndone] = useState<Point[]>([]);

  const canvas = useRef<HTMLCanvasElement>(null);
  const trace: CameraTrace | undefined = traces[camera];

  useEffect(() => {
    loadTraces()
      .then(setTraces)
      .catch(cause => setError(String(cause instanceof Error ? cause.message : cause)));
  }, []);

  // Editing always writes a new trace rather than mutating the loaded one,
  // so an abandoned edit cannot leave the file half-changed in memory.
  const update = useCallback((change: (t: CameraTrace) => CameraTrace) => {
    setTraces(all => (all[camera] ? { ...all, [camera]: change(all[camera]) } : all));
    setDirty(true);
    setStatus(null);
  }, [camera]);

  const road = trace?.tracks[roadIndex];
  const region = trace?.regions[regionIndex];

  const activePoints: Point[] = useMemo(() => {
    if (mode === 'rails') return road?.rails[rail] ?? [];
    if (mode === 'regions') return region?.points ?? [];
    return [];
  }, [mode, road, rail, region]);

  /** Where a click landed, in the frame's own coordinates. */
  const toFrame = (event: React.PointerEvent): Point => {
    const box = event.currentTarget.getBoundingClientRect();
    return [
      Math.round(((event.clientX - box.left) / box.width) * FRAME_WIDTH),
      Math.round(((event.clientY - box.top) / box.height) * FRAME_HEIGHT),
    ];
  };

  const addPoint = (event: React.PointerEvent) => {
    if (!trace) return;
    const point = toFrame(event);
    setUndone([]);
    if (mode === 'mask') {
      const grid = trace.mask_cells?.grid ?? [32, 18];
      const column = Math.min(grid[0] - 1, Math.floor((point[0] / FRAME_WIDTH) * grid[0]));
      const row = Math.min(grid[1] - 1, Math.floor((point[1] / FRAME_HEIGHT) * grid[1]));
      const cell = row * grid[0] + column;
      update(t => {
        const cells = new Set(t.mask_cells?.cells ?? []);
        // Painting toggles: the same tap takes a cell out again, which is
        // how a mistake is undone without hunting for it in a list.
        if (cells.has(cell)) cells.delete(cell); else cells.add(cell);
        return { ...t, mask_cells: { grid, cells: [...cells].sort((x, y) => x - y) } };
      });
      return;
    }
    if (mode === 'rails') {
      update(t => {
        const tracks = t.tracks.length ? [...t.tracks] : [
          { name: 'running line', kind: 'running' as const, rails: { a: [], b: [] } }];
        const at = Math.min(roadIndex, tracks.length - 1);
        const current = tracks[at];
        tracks[at] = { ...current,
          rails: { ...current.rails, [rail]: [...current.rails[rail], point] } };
        return { ...t, tracks };
      });
      return;
    }
    update(t => {
      const regions = t.regions.length ? [...t.regions] : [
        { name: 'platform', kind: 'platform' as const, points: [] }];
      const at = Math.min(regionIndex, regions.length - 1);
      regions[at] = { ...regions[at], points: [...regions[at].points, point] };
      return { ...t, regions };
    });
  };

  const undo = () => {
    if (!activePoints.length) return;
    const last = activePoints[activePoints.length - 1];
    setUndone(u => [...u, last]);
    replacePoints(activePoints.slice(0, -1));
  };

  const redo = () => {
    if (!undone.length) return;
    const point = undone[undone.length - 1];
    setUndone(u => u.slice(0, -1));
    replacePoints([...activePoints, point]);
  };

  const replacePoints = (points: Point[]) => {
    update(t => {
      if (mode === 'rails') {
        const tracks = [...t.tracks];
        if (!tracks[roadIndex]) return t;
        tracks[roadIndex] = { ...tracks[roadIndex],
          rails: { ...tracks[roadIndex].rails, [rail]: points } };
        return { ...t, tracks };
      }
      const regions = [...t.regions];
      if (!regions[regionIndex]) return t;
      regions[regionIndex] = { ...regions[regionIndex], points };
      return { ...t, regions };
    });
  };

  const save = async () => {
    try {
      const count = await saveTraces(traces);
      setDirty(false);
      setError(null);
      setStatus(`Saved — ${count} cameras, ${countPoints(trace!)} points on this one`);
    } catch (cause) {
      setError(String(cause instanceof Error ? cause.message : cause));
    }
  };

  // --- drawing -------------------------------------------------------
  useEffect(() => {
    const surface = canvas.current;
    if (!surface || !trace) return;
    surface.width = FRAME_WIDTH;
    surface.height = FRAME_HEIGHT;
    const ctx = surface.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, FRAME_WIDTH, FRAME_HEIGHT);

    if (trace.mask_cells) {
      const [columns, rows] = trace.mask_cells.grid;
      const cw = FRAME_WIDTH / columns;
      const ch = FRAME_HEIGHT / rows;
      // Faint unless it is what is being edited. Williton 2 has 68% of its
      // frame blocked, and at full strength the wash hid the rails being
      // traced over it.
      ctx.fillStyle = mode === 'mask'
        ? 'rgba(255, 90, 82, 0.34)'
        : 'rgba(255, 90, 82, 0.10)';
      for (const cell of trace.mask_cells.cells) {
        ctx.fillRect((cell % columns) * cw, Math.floor(cell / columns) * ch, cw, ch);
      }
      if (mode === 'mask') {
        ctx.strokeStyle = 'rgba(255,255,255,0.16)';
        ctx.lineWidth = 1;
        for (let c = 1; c < columns; c++) {
          ctx.beginPath(); ctx.moveTo(c * cw, 0); ctx.lineTo(c * cw, FRAME_HEIGHT); ctx.stroke();
        }
        for (let r = 1; r < rows; r++) {
          ctx.beginPath(); ctx.moveTo(0, r * ch); ctx.lineTo(FRAME_WIDTH, r * ch); ctx.stroke();
        }
      }
    }

    for (const shape of trace.regions) {
      if (shape.points.length < 2) continue;
      ctx.beginPath();
      shape.points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = `${REGION_COLOURS[shape.kind] ?? '#79e3a5'}33`;
      ctx.strokeStyle = REGION_COLOURS[shape.kind] ?? '#79e3a5';
      ctx.lineWidth = 2;
      ctx.fill();
      ctx.stroke();
    }

    trace.tracks.forEach(track => {
      (['a', 'b'] as const).forEach(side => {
        const points = track.rails[side];
        if (!points.length) return;
        ctx.strokeStyle = RAIL_COLOURS[side];
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.stroke();
        ctx.fillStyle = RAIL_COLOURS[side];
        for (const [x, y] of points) {
          ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill();
        }
      });
    });
  }, [trace, mode]);

  if (error && !Object.keys(traces).length) {
    return (
      <div className={admin.panel}>
        <h2>Annotations unavailable</h2>
        <p className={styles.hint}>{error}</p>
      </div>
    );
  }
  if (!trace) return <div className={admin.panel}>Loading annotations…</div>;

  return (
    <div className={styles.layout}>
      <div className={styles.bar}>
        <select
          className={styles.select}
          value={camera}
          onChange={e => {
            setCamera(e.target.value);
            setRoadIndex(0);
            setRegionIndex(0);
            setParams(next => {
              const q = new URLSearchParams(next);
              q.set('camera', e.target.value);
              return q;
            }, { replace: true });
          }}
          aria-label="Camera"
        >
          {CAMERAS.map(c => (
            <option key={c.id} value={c.id}>
              {c.name}{traces[c.id] && !isReady(traces[c.id]) ? ' — no track traced' : ''}
            </option>
          ))}
        </select>

        {(['rails', 'regions', 'mask'] as Mode[]).map(m => (
          <button
            key={m}
            className={`${styles.chip} ${mode === m ? styles.chipOn : ''}`}
            onClick={() => setMode(m)}
          >
            {m === 'rails' ? 'Rails' : m === 'regions' ? 'Platforms' : 'Blocked areas'}
          </button>
        ))}

        <span className={styles.grow} />

        <button className={styles.chip} onClick={undo} disabled={!activePoints.length}>
          <Undo2 size={13} aria-hidden /> Undo
        </button>
        <button className={styles.chip} onClick={redo} disabled={!undone.length}>
          <Redo2 size={13} aria-hidden /> Redo
        </button>
        <button className={styles.save} onClick={save} disabled={!dirty}>
          <Save size={13} aria-hidden /> Save
        </button>
      </div>

      {mode === 'rails' && (
        <div className={styles.bar}>
          <select
            className={styles.select}
            value={roadIndex}
            onChange={e => setRoadIndex(Number(e.target.value))}
            aria-label="Road"
          >
            {trace.tracks.map((t, i) => (
              <option key={i} value={i}>{t.name} ({t.kind})</option>
            ))}
            {!trace.tracks.length && <option value={0}>running line</option>}
          </select>
          {(['a', 'b'] as const).map(side => (
            <button
              key={side}
              className={`${styles.chip} ${rail === side ? styles.chipOn : ''}`}
              onClick={() => setRail(side)}
            >
              Rail {side.toUpperCase()} ({road?.rails[side].length ?? 0})
            </button>
          ))}
          <button
            className={styles.chip}
            onClick={() => update(t => ({
              ...t,
              tracks: [...t.tracks, {
                name: `road ${t.tracks.length + 1}`, kind: 'siding', rails: { a: [], b: [] },
              }],
            }))}
          >
            Add road
          </button>
          <button className={styles.chip} onClick={() => replacePoints([])}>
            <Trash2 size={13} aria-hidden /> Clear rail
          </button>
        </div>
      )}

      {mode === 'regions' && (
        <div className={styles.bar}>
          <select
            className={styles.select}
            value={regionIndex}
            onChange={e => setRegionIndex(Number(e.target.value))}
            aria-label="Region"
          >
            {trace.regions.map((r, i) => (
              <option key={i} value={i}>{r.kind} ({r.points.length} pts)</option>
            ))}
            {!trace.regions.length && <option value={0}>platform</option>}
          </select>
          {(['platform', 'occluder'] as const).map(kind => (
            <button
              key={kind}
              className={styles.chip}
              onClick={() => update(t => ({
                ...t,
                regions: [...t.regions, { name: kind, kind, points: [] }],
              }))}
            >
              Add {kind === 'platform' ? 'platform' : 'obstruction'}
            </button>
          ))}
          <button className={styles.chip} onClick={() => replacePoints([])}>
            <Trash2 size={13} aria-hidden /> Clear shape
          </button>
        </div>
      )}

      <div className={styles.stage}>
        <img
          className={styles.frame}
          src={`${import.meta.env.BASE_URL}reference/cam_${camera}.jpg`}
          alt=""
          onLoad={() => setFrameOk(true)}
          onError={() => setFrameOk(false)}
        />
        {!frameOk && (
          <p className={styles.missing}>
            No reference frame for this camera yet. One is written the first time
            the watcher sees it.
          </p>
        )}
        <canvas ref={canvas} className={styles.paint} onPointerDown={addPoint} />
      </div>

      <div className={styles.bar}>
        <span className={styles.status}>
          Towards Minehead is the
        </span>
        {(['start', 'end'] as const).map(which => (
          <button
            key={which}
            className={`${styles.chip} ${trace.minehead_end === which ? styles.chipOn : ''}`}
            onClick={() => update(t => ({ ...t, minehead_end: which }))}
          >
            {which} of the trace
          </button>
        ))}
        <span className={styles.grow} />
        <span className={`${styles.status} ${dirty ? styles.dirty : ''}`}>
          {error ? <span className={styles.error}>{error}</span>
            : status ?? (dirty ? 'Unsaved changes' : `${countPoints(trace)} points`)}
        </span>
      </div>

      <div className={styles.legend}>
        <span className={styles.key}>
          <span className={styles.swatch} style={{ background: RAIL_COLOURS.a }} /> rail A
        </span>
        <span className={styles.key}>
          <span className={styles.swatch} style={{ background: RAIL_COLOURS.b }} /> rail B
        </span>
        <span className={styles.key}>
          <span className={styles.swatch} style={{ background: REGION_COLOURS.platform }} /> platform
        </span>
        <span className={styles.key}>
          <span className={styles.swatch} style={{ background: REGION_COLOURS.occluder }} /> blocks the view
        </span>
        <span className={styles.key}>
          <span className={styles.swatch} style={{ background: 'rgba(255,90,82,0.5)' }} /> not looked at
        </span>
      </div>

      <p className={styles.hint}>
        Click along each rail from the Bishops Lydeard end towards Minehead — the
        two rails give the gauge, which is what turns pixels into metres. Blocked
        areas are painted by the cell and are where the detector will not look;
        tapping a painted cell takes it out again.
      </p>
    </div>
  );
};
