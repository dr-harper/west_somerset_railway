#!/bin/zsh
# Launcher for the scheduled watcher run.
#
# A LaunchAgent starts with almost no environment, so the interpreter is
# named in full rather than found on PATH, and the working directory is
# set explicitly — the watcher resolves captures/, weights and
# camera_tracks.json relative to itself.
#
# Output is appended, never truncated: a run that dies at 09:00 and is
# restarted must not erase the morning's evidence.

set -u

HERE="${0:A:h}"
cd "$HERE" || exit 1

PYTHON=/opt/anaconda3/bin/python3
HOURS="${WSR_HOURS:-11}"

echo "=== watcher starting $(date '+%Y-%m-%d %H:%M:%S') for ${HOURS}h ===" \
  >> watcher.log

"$PYTHON" -u gala_watcher.py --hours "$HOURS" >> watcher.log 2>&1
STATUS=$?

echo "=== watcher exited ${STATUS} at $(date '+%Y-%m-%d %H:%M:%S') ===" \
  >> watcher.log
exit $STATUS
