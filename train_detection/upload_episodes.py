"""Upload detected episodes to Firestore for manual verification.

The detection pipeline writes with the admin SDK, so security rules can
keep clients from creating or altering detection data — they may only set
the verification fields. This mirrors the server-writes-only pattern used
for the football-team-picker error stats.

Against the emulator (no credentials needed):
    FIRESTORE_EMULATOR_HOST=localhost:8085 \\
    python3 upload_episodes.py --project demo-wsr

Against a real project:
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \\
    python3 upload_episodes.py --project <project-id>

Episode media stays on disk by default: clips are training data, not
review material. --with-images uploads the keyframe and hi-res still to
Cloud Storage and stores their paths.
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
CAPTURES = HERE / 'captures'
COLLECTION = 'episodes'


def episode_document(episode: dict, movement: dict | None) -> dict:
    """One Firestore document: what was detected, and what we think it was."""
    scheduled = (movement or {}).get('scheduled')
    return {
        # --- detection facts (pipeline-owned, clients cannot change) ---
        'camera': episode['camera'],
        't_enter': episode['t_enter'],
        't_exit': episode.get('t_exit'),
        'date_key': episode['t_enter'][:10],
        'direction': episode.get('direction'),
        'zones': episode.get('zones', []),
        'peak_conf': episode.get('peak_conf'),
        'observations': episode.get('n_observations'),
        'drift_px': episode.get('drift_px'),
        'keyframe': (episode.get('keyframes') or [None])[0],
        'hires': episode.get('hires'),
        'clip': episode.get('clip'),

        # --- the system's claim, for a human to confirm or correct ---
        'claim': {
            'kind': 'scheduled' if scheduled else 'unscheduled',
            'booked_departure': scheduled.get('booked_departure') if scheduled else None,
            'serviceType': scheduled.get('serviceType') if scheduled else None,
            'loco': scheduled.get('loco') if scheduled else None,
            'delay_min': scheduled.get('delay_min') if scheduled else None,
            'corroborating_sightings': (movement or {}).get('sightings'),
        },

        'uploaded_at': datetime.now().isoformat(timespec='seconds'),
    }


# Verification state lives in its own fields so a re-upload can refresh the
# detection claim without discarding a human's answer.
INITIAL_VERIFICATION = {'status': 'unverified', 'verification': None}


def episode_id(episode: dict) -> str:
    """Stable id so re-running the uploader updates rather than duplicates."""
    return f"{episode['t_enter'].replace(':', '').replace('-', '')}_{episode['camera']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--date', default=None, help='only upload this date_key')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    from episode_analysis import load_episodes
    from movement_tracker import annotate, build_movements

    episodes = load_episodes()
    if args.date:
        episodes = [e for e in episodes if e['t_enter'].startswith(args.date)]
    if not episodes:
        print('no episodes to upload')
        return

    # map each episode to the movement that explains it, so the uploaded
    # claim carries the corroborated view rather than a lone sighting
    date_key = episodes[0]['t_enter'][:10]
    movements = build_movements(episodes)
    annotated = annotate(movements, date_key)
    claim_for: dict[str, dict] = {}
    for movement, record in zip(movements, annotated):
        for obs in movement['_chain']:
            claim_for[obs['episode']['t_enter']] = {**record,
                                                    'sightings': movement['sightings']}

    documents = [(episode_id(e), episode_document(e, claim_for.get(e['t_enter'])))
                 for e in episodes]
    scheduled = sum(1 for _, d in documents if d['claim']['kind'] == 'scheduled')
    print(f'{len(documents)} episodes '
          f'({scheduled} scheduled, {len(documents) - scheduled} unscheduled)')

    if args.dry_run:
        for doc_id, doc in documents[:3]:
            print(f'  {doc_id}: {doc["claim"]}')
        print('dry run — nothing written')
        return

    import firebase_admin
    from firebase_admin import firestore

    if os.environ.get('FIRESTORE_EMULATOR_HOST'):
        print(f"using emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}")
        firebase_admin.initialize_app(options={'projectId': args.project})
    else:
        firebase_admin.initialize_app(options={'projectId': args.project})

    client = firestore.client()
    collection = client.collection(COLLECTION)
    existing = {snapshot.id for snapshot in collection.select([]).stream()}

    batch = client.batch()
    written = new = 0
    for doc_id, doc in documents:
        payload = dict(doc)
        if doc_id not in existing:
            payload.update(INITIAL_VERIFICATION)   # only ever set on create
            new += 1
        batch.set(collection.document(doc_id), payload, merge=True)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = client.batch()
    batch.commit()
    print(f'wrote {written} documents to {COLLECTION} '
          f'({new} new, {written - new} refreshed without touching verification)')


if __name__ == '__main__':
    main()
