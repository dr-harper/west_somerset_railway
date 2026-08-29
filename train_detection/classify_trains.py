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
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

HERE = Path(__file__).parent
load_dotenv(HERE / '.env')

MODEL = 'gemini-2.5-flash'

PROMPT = (
    'This is a photograph of a train on the West Somerset Railway, a British '
    'heritage line. Classify it. traction: steam locomotive, diesel '
    'locomotive, or DMU (diesel multiple unit — a self-propelled passenger '
    'unit with a cab at coach level, no separate locomotive). livery: the '
    'dominant colour scheme of the locomotive or unit. notes: anything '
    'distinctive (visible number, headboard, exhaust, unusual stock).'
)


class TrainClassification(BaseModel):
    traction: str          # 'steam' | 'diesel' | 'dmu' | 'unsure'
    livery: str
    confidence: float      # 0-1, the model's own estimate
    notes: str


def _crop(image_path: Path, box: list[int] | None, pad: float = 0.15) -> bytes:
    img = Image.open(image_path).convert('RGB')
    if box:
        x1, y1, x2, y2 = box
        # boxes are in 854x480 coords; scale to this image's size
        sx, sy = img.width / 854, img.height / 480
        w, h = (x2 - x1) * sx, (y2 - y1) * sy
        img = img.crop((
            max(0, x1 * sx - w * pad), max(0, y1 * sy - h * pad),
            min(img.width, x2 * sx + w * pad), min(img.height, y2 * sy + h * pad),
        ))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()


def classify_image(image_path: Path, box: list[int] | None = None) -> TrainClassification:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=_crop(image_path, box), mime_type='image/jpeg'),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=TrainClassification,
        ),
    )
    return TrainClassification.model_validate(response.parsed)


def classify_episode(episode: dict, captures_dir: Path = HERE / 'captures') -> dict:
    """Classify an episode from its hi-res still (fall back to a keyframe)."""
    image = None
    for name in [episode.get('hires'), *reversed(episode.get('keyframes', []))]:
        if name and (captures_dir / name).exists():
            image = captures_dir / name
            break
    if image is None:
        return {**episode, 'classification': None}
    result = classify_image(image)
    return {**episode, 'classification': result.model_dump()}


if __name__ == '__main__':
    from episode_analysis import load_episodes
    episodes = load_episodes()
    print(f'{len(episodes)} episodes to classify')
    for ep in episodes:
        out = classify_episode(ep)
        c = out['classification']
        print(ep['t_enter'], ep['camera'], '->',
              json.dumps(c) if c else 'no image available')
