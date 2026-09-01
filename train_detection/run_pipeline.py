"""Classify what the watcher found, then push it to the live project.

Both halves were run by hand, so the control room was routinely hours
behind what the cameras had already seen, and on 30/8 the classifier simply
stopped being run at all — 549 episodes reached the site with 220 readings
between them because nobody remembered.

Invoked straight by launchd as a Python program rather than through a shell
wrapper. The watcher's own agent records why: a wrapper script failed to
spawn with exit 127 and lost the 08:00 start, and pointing a job's log
inside the project directory failed with EX_CONFIG and lost another. Both
lessons are honoured here.

Credentials are minted per run from the gcloud login rather than kept as a
key on disk. The laptop's ambient credentials belong to a different Google
account entirely, so something has to say which one — and a short-lived
token that is fetched, used and forgotten beats a service account key
sitting in a file forever.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent

# Whose credentials to use. Not the machine's default: that is the work
# account, which has no access to this project and produces a permission
# error naming the wrong user.
ACCOUNT = 'mikeylharper@gmail.com'
PROJECT = 'west-somerset-railway-project'


def say(message: str) -> None:
    print(f'{datetime.now():%Y-%m-%d %H:%M:%S}  {message}', flush=True)


def access_token(account: str) -> str | None:
    """A fresh token, or None if the login has lapsed and needs a human."""
    try:
        done = subprocess.run(
            ['gcloud', 'auth', 'print-access-token', f'--account={account}'],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        say(f'could not run gcloud: {error}')
        return None
    if done.returncode != 0:
        say(f'gcloud refused: {done.stderr.strip()[:200]}')
        return None
    return done.stdout.strip() or None


def run(name: str, args: list[str], env: dict) -> bool:
    """One step, with its output kept whatever happens."""
    say(f'--- {name} ---')
    done = subprocess.run([sys.executable, '-u', *args], cwd=HERE, env=env,
                          capture_output=True, text=True)
    for line in (done.stdout or '').splitlines()[-12:]:
        print(f'    {line}', flush=True)
    if done.returncode != 0:
        # The tail of stderr, because the useful part of a traceback is the
        # end of it and the whole thing buries the reason.
        for line in (done.stderr or '').splitlines()[-8:]:
            print(f'    ! {line}', flush=True)
        say(f'{name} failed ({done.returncode})')
        return False
    say(f'{name} ok')
    return True


def main() -> int:
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument('--account', default=ACCOUNT)
    parser.add_argument('--project', default=PROJECT)
    parser.add_argument('--date', default=None,
                        help='limit classification to one date_key')
    parser.add_argument('--skip-classify', action='store_true')
    args = parser.parse_args()

    token = access_token(args.account)
    if not token:
        say(f'no credentials for {args.account}; run '
            f'"gcloud auth login {args.account}" and this will resume on its '
            f'own at the next run')
        return 1

    env = {**os.environ, 'WSR_ACCESS_TOKEN': token}

    ok = True
    # Classification first, so the upload that follows carries the readings
    # rather than leaving them for whenever it next runs.
    if not args.skip_classify:
        classify = ['classify_trains.py']
        if args.date:
            classify += ['--date', args.date]
        ok = run('classify', classify, env) and ok

    # --media is what puts the stills and clips where the deployed control
    # room can read them. Without it the documents arrive pointing at files
    # that exist only on this laptop.
    ok = run('upload', ['upload_episodes.py', '--project', args.project,
                        '--media'], env) and ok

    say('done' if ok else 'finished with failures')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
