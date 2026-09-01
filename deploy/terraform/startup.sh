#!/bin/bash
# Brings the machine up ready to watch the railway. Runs on every boot, so
# everything here has to be safe to repeat.
set -euo pipefail

BUCKET="${bucket}"
PROJECT="${project_id}"
START_HOUR="${start_hour}"
HOURS="${hours}"

if [ ! -f /opt/wsr/.provisioned ]; then
  apt-get update
  # ffmpeg for the HLS streams, python for everything else. No display, so
  # opencv-python-headless rather than the full package.
  apt-get install -y python3 python3-pip python3-venv ffmpeg git nodejs npm
  mkdir -p /opt/wsr
  python3 -m venv /opt/wsr/venv
  /opt/wsr/venv/bin/pip install --upgrade pip
  /opt/wsr/venv/bin/pip install \
    opencv-python-headless ultralytics yt-dlp google-cloud-firestore \
    google-cloud-storage numpy scipy
  touch /opt/wsr/.provisioned
fi

# The timezone matters: the watcher starts at a local hour, and the railway
# runs to British time whatever the machine thinks.
timedatectl set-timezone Europe/London

# The Gemini key is fetched at start and held in a file only root and the
# service can read, rather than baked into the image or committed anywhere.
# Refetching each start means rotating the secret is a restart, not a rebuild.
install -d -m 0700 /run/wsr
gcloud secrets versions access latest \
  --secret=gemini-api-key --project="$PROJECT" > /run/wsr/gemini.key 2>/dev/null \
  && chmod 0600 /run/wsr/gemini.key \
  || echo "no gemini-api-key in Secret Manager yet; classification will be skipped"

cat >/etc/systemd/system/wsr-watcher.service <<UNIT
[Unit]
Description=West Somerset Railway monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/wsr/app/train_detection
Environment=GCLOUD_PROJECT=$PROJECT
Environment=WSR_CAPTURE_BUCKET=$BUCKET
# node is what yt-dlp needs to answer YouTube's player challenge. Losing it
# from PATH is how a morning was lost once already.
Environment=PATH=/opt/wsr/venv/bin:/usr/local/bin:/usr/bin:/bin
# Read from the file rather than passed as an environment string, so the key
# does not appear in the unit file, in `systemctl show`, or in the process
# listing.
Environment=GEMINI_API_KEY_FILE=/run/wsr/gemini.key
ExecStart=/opt/wsr/venv/bin/python -u gala_watcher.py --hours $HOURS
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT

# Started by a timer rather than at boot, so a reboot at midnight does not
# spend eleven hours watching an empty railway.
cat >/etc/systemd/system/wsr-watcher.timer <<TIMER
[Unit]
Description=Start the monitor when the line does

[Timer]
OnCalendar=*-*-* $START_HOUR:00:00
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable wsr-watcher.timer
systemctl start wsr-watcher.timer
