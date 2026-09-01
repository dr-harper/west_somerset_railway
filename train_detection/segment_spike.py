"""Can the run-up be kept as H.264 segments instead of decoded JPEGs?

A frame costs 120KB as JPEG and about 5KB inside an H.264 clip, because
these cameras never move and almost every frame is nearly the one before
it. JPEG throws that away thirty times a second; H.264 keeps only what
changed. The stream arriving from YouTube is already H.264, so buffering
the compressed bytes means the encoding is work somebody else has already
done.

The catch is that H.264 cannot be cut anywhere. A predicted frame is
meaningless without the frames it was predicted from, so a buffer has to
be whole segments, each starting at a keyframe. This measures what that
costs us in practice:

  - how long a segment really is, which sets how precisely a run-up can
    start
  - how many bytes a frame really takes on these streams
  - whether concatenated segments play as one clip

    python3 segment_spike.py --camera blue_anchor_2 --seconds 40
"""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from wsr_live_capture import resolve_hls_url

HERE = Path(__file__).parent
WORK = HERE / 'segment_spike'


def probe(path: Path) -> dict:
    """Frame types and sizes, straight from the container."""
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'frame=pict_type,pkt_size',
         '-show_entries', 'format=duration,size',
         '-of', 'json', str(path)],
        capture_output=True, text=True)
    if out.returncode:
        return {}
    return json.loads(out.stdout or '{}')


def summarise(path: Path) -> dict:
    data = probe(path)
    frames = data.get('frames', [])
    if not frames:
        return {}
    kinds: dict[str, list] = {}
    for frame in frames:
        kinds.setdefault(frame.get('pict_type', '?'), []).append(
            int(frame.get('pkt_size') or 0))
    duration = float(data.get('format', {}).get('duration') or 0)
    size = int(data.get('format', {}).get('size') or 0)
    # The gap between keyframes is what a run-up can be cut to.
    gop = len(frames) / max(1, len(kinds.get('I', [])))
    return {
        'frames': len(frames),
        'duration': duration,
        'size': size,
        'per_frame': size / max(1, len(frames)),
        'gop': gop,
        'kinds': {k: {'n': len(v), 'mean': sum(v) / max(1, len(v))}
                  for k, v in sorted(kinds.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', default='blue_anchor_2')
    parser.add_argument('--seconds', type=float, default=40.0)
    parser.add_argument('--segment', type=float, default=2.0)
    parser.add_argument('--keep', type=int, default=8)
    args = parser.parse_args()

    if not shutil.which('ffmpeg'):
        print('ffmpeg is not installed')
        return

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    print(f'resolving {args.camera} ...')
    url = resolve_hls_url(args.camera)
    if not url:
        print('  no stream url')
        return

    # -c copy is the whole point: the compressed frames are written out
    # exactly as they arrived, so nothing is decoded and nothing re-encoded.
    # -segment_wrap turns the directory into a ring by reusing the names.
    command = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-i', url,
        '-c', 'copy',
        '-f', 'segment',
        '-segment_time', str(args.segment),
        '-segment_wrap', str(args.keep),
        '-reset_timestamps', '1',
        str(WORK / 'seg_%03d.ts'),
    ]
    print(f'recording {args.seconds:.0f}s in {args.segment:.0f}s segments, '
          f'keeping {args.keep} ...')
    started = time.time()
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    try:
        while time.time() - started < args.seconds:
            time.sleep(2)
            segments = sorted(WORK.glob('seg_*.ts'))
            total = sum(s.stat().st_size for s in segments)
            print(f'  {time.time() - started:>5.1f}s  {len(segments)} segments  '
                  f'{total / 1e6:>5.2f} MB on disk')
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    segments = sorted(WORK.glob('seg_*.ts'))
    if not segments:
        print('\nno segments written')
        err = process.stderr.read().decode()[:400] if process.stderr else ''
        print(err)
        return

    print(f'\n{len(segments)} segments held — this is the whole buffer')
    for segment in segments[:3]:
        info = summarise(segment)
        if not info:
            continue
        kinds = ', '.join(f"{k}×{v['n']} at {v['mean'] / 1024:.1f}KB"
                          for k, v in info['kinds'].items())
        print(f"  {segment.name}: {info['duration']:.1f}s, {info['frames']} frames, "
              f"{info['size'] / 1024:.0f}KB, {info['per_frame'] / 1024:.1f}KB/frame")
        print(f"      keyframe every ~{info['gop']:.0f} frames | {kinds}")

    # Does a run-up assembled from segments actually play?
    # The newest segment is the one ffmpeg was mid-way through, so it is
    # left out. A real buffer has the same property: the segment being
    # written is not yet part of the run-up.
    complete = [s for s in segments if s.stat().st_size > 0][:-1] or segments[:1]
    listing = WORK / 'list.txt'
    listing.write_text('\n'.join(f"file '{s.resolve()}'" for s in complete))
    joined = WORK / 'runup.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'concat', '-safe', '0', '-i', str(listing),
                    '-c', 'copy', str(joined)], check=False)
    print(f'\njoined {len(complete)} complete segments '
          f'(newest left out — still being written)')
    info = summarise(joined)
    if info:
        print(f"\nconcatenated run-up: {info['duration']:.1f}s, {info['frames']} frames, "
              f"{info['size'] / 1e6:.2f} MB")
        jpeg = info['frames'] * 120 * 1024
        print(f"  the same frames as JPEG would be {jpeg / 1e6:.1f} MB "
              f"— {jpeg / max(1, info['size']):.0f}x larger")
        print(f"\n15s across 11 cameras at this rate: "
              f"{info['per_frame'] * 30 * 15 * 11 / 1e6:.1f} MB "
              f"(as JPEG q70 it would be {120 * 1024 * 30 * 15 * 11 / 1e9:.2f} GB)")
    else:
        print('\nconcatenation produced nothing readable')


if __name__ == '__main__':
    main()
