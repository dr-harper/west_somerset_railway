"""Push the stills and clips an episode refers to into Cloud Storage.

The uploader's docstring has promised a --with-images flag since it was
written; nothing implemented it, so every episode reaching Firestore named
a keyframe that existed only on the laptop that recorded it. Deployed, the
control room rendered perfectly and showed a grid of broken frames — the
same failure mode as the base-path bug, and just as quiet.

Only what an episode actually names is uploaded. The captures directory
also holds working stills, discarded frames and the annotator's own
scratch files, and none of that is review material.

The bucket is private. These are frames lifted from Railcam's public
streams: the observations drawn from them are facts about the railway and
are published freely, the footage is somebody else's work. storage.rules
gates reads on the operator grant.
"""

import mimetypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
CAPTURES = HERE / 'captures'

# Matches the prefix in storage.rules and the one the web app asks for.
PREFIX = 'captures'

# The fields on an episode document that name a file on disk.
MEDIA_FIELDS = ('keyframe', 'hires', 'clip', 'dense_clip')

# Names are unique per episode — a timestamp, a camera and a role — so a
# file at a given name never changes. Anything that does fetch it can keep
# it for as long as it likes.
CACHE_CONTROL = 'private, max-age=31536000, immutable'

# Enough to keep the link busy without opening a connection per episode.
WORKERS = 8


def referenced(documents) -> list[str]:
    """Every file named by these episode documents, in a stable order."""
    names: dict[str, None] = {}          # dict, not set, to keep order
    for _doc_id, doc in documents:
        for field in MEDIA_FIELDS:
            name = doc.get(field)
            if name:
                names[name] = None
    return list(names)


def existing(bucket) -> set[str]:
    """What is already up there.

    Listed once rather than probed per file: 2,000 existence checks is
    2,000 round trips, and one listing answers all of them.
    """
    return {blob.name[len(PREFIX) + 1:]
            for blob in bucket.list_blobs(prefix=f'{PREFIX}/')}


def upload(bucket, names, dry_run: bool = False, workers: int = WORKERS) -> dict:
    """Upload the named files that are not up there already.

    Idempotent on purpose: this runs after every detection pass, and a
    re-upload of a day's footage costs real money and real time for no
    change at all.
    """
    already = set() if dry_run else existing(bucket)

    missing_locally, to_send = [], []
    for name in names:
        if name in already:
            continue
        path = CAPTURES / name
        # A named file that is not on disk is worth reporting rather than
        # skipping silently: it means an episode points at something the
        # pipeline did not keep.
        (to_send if path.is_file() else missing_locally).append((name, path))

    summary = {
        'named': len(names),
        'already': len(names) - len(to_send) - len(missing_locally),
        'sent': 0,
        'bytes': 0,
        'missing_locally': [n for n, _ in missing_locally],
    }

    if dry_run or not to_send:
        summary['sent'] = len(to_send) if dry_run else 0
        summary['bytes'] = sum(p.stat().st_size for _n, p in to_send)
        return summary

    def send(item) -> int:
        name, path = item
        blob = bucket.blob(f'{PREFIX}/{name}')
        blob.cache_control = CACHE_CONTROL
        content_type, _ = mimetypes.guess_type(name)
        blob.upload_from_filename(str(path), content_type=content_type)
        return path.stat().st_size

    with ThreadPoolExecutor(max_workers=workers) as pool:
        sizes = list(pool.map(send, to_send))

    summary['sent'] = len(sizes)
    summary['bytes'] = sum(sizes)
    return summary


def describe(summary: dict) -> str:
    megabytes = summary['bytes'] / 1_000_000
    parts = [f"{summary['named']} files named by episodes",
             f"{summary['already']} already up",
             f"{summary['sent']} sent ({megabytes:.0f} MB)"]
    if summary['missing_locally']:
        parts.append(f"{len(summary['missing_locally'])} named but not on disk")
    return ', '.join(parts)
