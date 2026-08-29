"""Per-episode train classification from the 1080p still, via Gemini with
structured output.

One call per episode (not per frame) keeps this at ~100 calls on the
busiest day. Requires GEMINI_API_KEY in train_detection/.env — and note
that key must be a NEW one: the original was exposed in git history and
should be treated as burned.
"""

import io
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

HERE = Path(__file__).parent
load_dotenv(HERE / '.env')

MODEL = 'gemini-2.5-flash'

# Traction is the field that matters most and the one the timetable gets
# wrong: a booked steam working is sometimes covered by a diesel and vice
# versa, so what is actually running can only come from the picture. It is
# a closed set, and asking for free text produced 'N/A' and 'not visible'
# alongside 'diesel locomotive' — three ways of saying nothing.
TRACTION = ('steam', 'diesel', 'dmu', 'unsure')

PROMPT = (
    'This is a still from a lineside camera on the West Somerset Railway, '
    'a British heritage line in Somerset. Identify the train.\n\n'
    'traction — the single most important field. One of: '
    '"steam" (an external-combustion locomotive with a boiler, chimney and '
    'visible steam or coal smoke); '
    '"diesel" (a diesel locomotive hauling separate unpowered coaches or '
    'wagons); '
    '"dmu" (diesel multiple unit — a self-propelled passenger set with a '
    'driving cab at coach roof level and no separate locomotive; often '
    'green or blue-grey, with a flat cab front and destination blind); '
    '"unsure" only if no locomotive or unit is visible at all. '
    'Judge from the leading vehicle. Coaches alone, or a rake with no '
    'visible motive power, is "unsure" — not a guess.\n\n'
    'train_class — the class or type if recognisable, in British practice: '
    'e.g. "Class 35 Hymek", "Class 33", "Class 14", "GWR 4575 Class", '
    '"GWR Manor Class", "Class 115 DMU". Empty string if not identifiable.\n\n'
    'number — the running number carried on the locomotive or unit, exactly '
    'as painted: e.g. "D7017", "D6566", "4875", "7812". Empty string unless '
    'you can actually read it.\n\n'
    'livery — the dominant colour scheme.\n\n'
    'confidence — your own confidence in the traction field, 0 to 1.\n\n'
    'notes — anything else distinctive: headboard, exhaust, unusual stock, '
    'whether it is moving or stabled.'
)


class TrainClassification(BaseModel):
    traction: str          # constrained to TRACTION by _normalise
    train_class: str       # e.g. 'Class 35 Hymek'; '' when not identifiable
    number: str            # e.g. 'D7017'; '' when not legible
    livery: str
    confidence: float      # 0-1, the model's own estimate
    notes: str


def _normalise(result: 'TrainClassification') -> 'TrainClassification':
    """Fold the model's wording back onto the closed set.

    It answers 'diesel locomotive' or 'DMU' as readily as the bare token,
    and occasionally 'N/A'. Anything unrecognised becomes 'unsure' rather
    than being carried through as a fourth kind of traction.
    """
    word = (result.traction or '').strip().lower()
    if 'dmu' in word or 'multiple unit' in word:
        traction = 'dmu'
    elif 'steam' in word:
        traction = 'steam'
    elif 'diesel' in word:
        traction = 'diesel'
    else:
        traction = 'unsure'
    number = re.sub(r'[^0-9A-Za-z]', '', (result.number or '')).upper()
    return result.model_copy(update={
        'traction': traction,
        # A running number is digits, optionally prefixed D or a class
        # letter. Anything else is the model narrating rather than reading.
        'number': number if re.fullmatch(r'[A-Z]?\d{3,5}', number) else '',
    })


def _crop(image_path: Path, box: list[int] | None,
          box_dims: tuple[int, int] | None = None, pad: float = 0.18) -> bytes:
    """The image, cropped to the detection if we know where it is.

    A full frame is mostly hedge, platform and sky, and the locomotive can
    be a fifth of its width — running numbers do not survive that. Boxes
    are recorded against a stated resolution, so they are scaled from that
    rather than from an assumed 854x480.
    """
    img = Image.open(image_path).convert('RGB')
    if box:
        source_w, source_h = box_dims or (854, 480)
        sx, sy = img.width / source_w, img.height / source_h
        x1, y1, x2, y2 = box
        w, h = (x2 - x1) * sx, (y2 - y1) * sy
        img = img.crop((
            max(0, x1 * sx - w * pad), max(0, y1 * sy - h * pad),
            min(img.width, x2 * sx + w * pad), min(img.height, y2 * sy + h * pad),
        ))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=92)
    return buf.getvalue()


def classify_image(image_path: Path, box: list[int] | None = None,
                   box_dims: tuple[int, int] | None = None) -> TrainClassification:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=_crop(image_path, box, box_dims),
                                  mime_type='image/jpeg'),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=TrainClassification,
        ),
    )
    return _normalise(TrainClassification.model_validate(response.parsed))


def _stills_for(episode: dict, captures_dir: Path) -> list[str]:
    """Every saved still for an episode, most likely to show traction first.

    The entry frame is the moment the train came into view, so it holds
    the leading vehicle; the hi-res grab is the sharpest; the keyframes
    follow. By the last of them a long train is usually all coaches.
    """
    names = [episode.get('entry_frame'), episode.get('hires'),
             *(episode.get('keyframes') or [])]
    seen, out = set(), []
    for name in names:
        if name and name not in seen and (captures_dir / name).exists():
            seen.add(name)
            out.append(name)
    return out


def classify_episode(episode: dict, captures_dir: Path = HERE / 'captures',
                     max_stills: int = 3) -> dict:
    """Classify from whichever still actually shows a locomotive.

    A single frame is a bad unit: an episode lasting a minute is mostly
    coaches, and a still of coaches honestly answers 'unsure'. Reading
    several and keeping the most confident identification is what turns
    that into an answer, without inventing one when there is genuinely no
    traction in view.
    """
    attempts = []
    for name in _stills_for(episode, captures_dir)[:max_stills]:
        record = (episode.get('boxes') or {}).get(name) or {}
        detections = record.get('detections') or []
        biggest = max(
            detections,
            key=lambda d: (d['box'][2] - d['box'][0]) * (d['box'][3] - d['box'][1]),
            default=None)
        try:
            result = classify_image(
                captures_dir / name,
                biggest['box'] if biggest else None,
                (record['width'], record['height']) if record else None)
        except Exception:
            continue
        attempts.append((name, result))
        # A confident, numbered identification is as good as it gets;
        # reading further stills of the same train only costs calls.
        if result.traction != 'unsure' and result.number:
            break

    if not attempts:
        return {**episode, 'classification': None}

    # Prefer an identification over a shrug, then the model's own
    # confidence, then one that managed to read a number.
    name, best = max(attempts, key=lambda pair: (
        pair[1].traction != 'unsure', bool(pair[1].number), pair[1].confidence))
    return {**episode, 'classification': best.model_dump(),
            'classified_from': name, 'stills_read': len(attempts)}


OUT_PATH = HERE / 'classifications.json'


def main() -> None:
    import argparse

    from episode_analysis import load_episodes

    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='classify only the first N')
    parser.add_argument('--date', help='only this date_key')
    args = parser.parse_args()

    episodes = load_episodes()
    if args.date:
        episodes = [e for e in episodes if e['t_enter'].startswith(args.date)]
    if args.limit:
        episodes = episodes[:args.limit]

    # Resume rather than re-ask: a rerun after a failure should cost only
    # the episodes that have not been answered yet.
    done = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    todo = [e for e in episodes if e['t_enter'] not in done]
    print(f'{len(episodes)} episodes, {len(done)} already classified, '
          f'{len(todo)} to do')

    for index, episode in enumerate(todo, 1):
        try:
            result = classify_episode(episode)['classification']
        except Exception as error:               # one bad still must not
            print(f'  {episode["t_enter"]} failed: {str(error)[:90]}')
            continue                             # end the whole run
        if result is None:
            continue
        done[episode['t_enter']] = {**result, 'camera': episode['camera']}
        print(f"[{index}/{len(todo)}] {episode['t_enter']:<20} "
              f"{episode['camera'][:22]:<22} {result['traction']:<7} "
              f"{result['number'] or '—':<7} {result['train_class'][:28]}")
        OUT_PATH.write_text(json.dumps(done, indent=1))

    print(f'\nwrote {len(done)} classifications to {OUT_PATH.name}')


if __name__ == '__main__':
    main()
