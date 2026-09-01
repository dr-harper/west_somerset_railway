"""Make someone an operator of the control room.

Membership lives in /verifiers and is granted out of band, never
self-served: the rules let a verifier set a detection's status and nothing
else, and let nobody grant themselves that.

Keyed by email rather than uid on purpose. A Firebase uid does not exist
until the person has signed in, so granting by uid alone means the first
operator can never be created — they have to sign in to get a uid, and be
refused because they have no grant.

    python3 grant_verifier.py --email you@example.com
    python3 grant_verifier.py --list
    python3 grant_verifier.py --revoke someone@example.com
"""

import argparse
import os
from datetime import datetime

COLLECTION = 'verifiers'


def client(project: str):
    from google.cloud import firestore
    if os.environ.get('FIRESTORE_EMULATOR_HOST'):
        print(f"using emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}")
    return firestore.Client(project=project)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default=os.environ.get('GCLOUD_PROJECT', 'demo-wsr'))
    parser.add_argument('--email')
    parser.add_argument('--revoke')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--note', default='')
    args = parser.parse_args()

    db = client(args.project)
    collection = db.collection(COLLECTION)

    if args.list:
        found = list(collection.stream())
        if not found:
            print('nobody can verify — the queue is read-only to everyone')
            return
        for doc in found:
            data = doc.to_dict() or {}
            print(f"  {doc.id:<40} granted {data.get('granted_at', '?')}"
                  f"{' — ' + data['note'] if data.get('note') else ''}")
        return

    if args.revoke:
        collection.document(args.revoke).delete()
        print(f'{args.revoke} can no longer verify')
        return

    if not args.email:
        parser.error('one of --email, --revoke or --list')

    collection.document(args.email).set({
        'granted_at': datetime.now().isoformat(timespec='seconds'),
        'granted_by': 'grant_verifier.py',
        'note': args.note or None,
    })
    print(f'{args.email} can now verify detections on project {args.project}')


if __name__ == '__main__':
    main()
