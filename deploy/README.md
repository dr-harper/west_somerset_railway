# Deploying the monitor

Notes on where the monitor runs and why. Written 31 August 2026, revised
1 September after the VM turned out not to be able to see the streams.

## The finding that shaped this

**YouTube serves the HLS manifest to a datacentre and refuses the media.**
Measured on 1/9 from a GCP VM in europe-west2 against three cameras: the
playlist returns 200 and about 7 KB every time, and the first segment
302s to a second host which answers 403. The same code, same cameras,
minutes apart on a home connection returned 200 and 490 KB.

It is the source address. Not IPv6 — the VM has no IPv6 route and egress is
IPv4. Not yt-dlp, not the player challenge, not the code.

`yt-dlp -g` resolving cleanly is *not* evidence the streams work; it only
proves the index is readable. Fetch a segment before believing it.

So capture runs where the address is residential, and everything that does
work from the cloud stays in the cloud.

## Why

The monitor currently runs on a MacBook. That has cost two mornings already
— a scheduled job that failed silently, and a network change that pointed the
control room at a machine that no longer existed — and it stops entirely
whenever the laptop is shut. A gala day missed is not recoverable.

## Accounts, and a trap

This laptop's ambient credentials belong to `michael@heatgeek.com`, the work
account, on project `skoon-zor-dev`. The monitor lives on the personal
account. Anything reaching this project from here has to say so explicitly
or it fails with a permission error naming the wrong user:

```bash
WSR_ACCESS_TOKEN=$(gcloud auth print-access-token --account=mikeylharper@gmail.com)
terraform plan   # via GOOGLE_OAUTH_ACCESS_TOKEN, same idea
```

`run_pipeline.py` mints one per run rather than keeping a service account
key on disk. Switching the machine's active account would work too, and
would disturb whatever the work account is in the middle of.

## What it needs, measured

Timed on this codebase rather than estimated. Per frame, at 854x480:

| work | cost | rate | per camera |
|---|---|---|---|
| H.264 decode | 0.74 ms | 30 fps | 22 ms/s |
| JPEG encode (frame ring) | 0.62 ms | 30 fps | 19 ms/s |
| motion gate | 0.18 ms | 2 Hz | 0.4 ms/s |
| YOLO | 35 ms | 1 Hz, only while active | 35 ms/s |

**Eleven cameras: 0.52 vCPU.** The two-tier gate is what makes that fit —
inference is 190× the cost of the gate that decides whether to run it.

No GPU. CPU inference measured the same 35 ms as Apple's GPU, because the
model is small.

Memory is **2 GB** once the frame buffers are consolidated onto the ring.
Today the watcher holds raw frames in two more buffers and sits at 2 GB before
the ring is added, which is why the Terraform defaults to `e2-medium` (4 GB)
rather than `e2-small`. That default should come down after the consolidation
and roughly halves the compute bill.

## What it costs

- **Compute** — e2-medium always on in `europe-west2`, roughly £18–22/month.
  Dropping to e2-small after the buffer work takes it to around £10.
- **Storage** — captures arrive at 27.5 GB/month. Lifecycle rules cool them to
  Nearline at 14 days, Coldline at 45, and delete at 90. A few pounds, growing
  slowly.
- **Firestore** — free. 181 episodes a day at 2.3 KB is 143 MB a year against
  a 1 GiB free tier, and writes stay inside 20,000/day.

Rates are estimates. The vCPU sizing is measured; the conversion to money is
not, and should be checked against the calculator before applying.

## Shape

Split, for the reason above.

**Capture runs on the laptop.** Two LaunchAgents, versioned in
`deploy/local/` because they previously existed on one machine and in no
repository at all: `uk.co.wsr.watcher` starts at 08:00 and watches for
eleven hours, `uk.co.wsr.pipeline` classifies and uploads every fifteen
minutes.

**Everything else is in GCP.** Firestore holds the detections, the bucket
holds the stills and clips, Secret Manager holds the Gemini key, Firebase
Hosting serves the site. None of that cares where the frames came from.

**The VM is stopped, not destroyed.** Terraform declares it
`TERMINATED` via `watcher_running = false`. The provisioning on its disk is
sound and will be wanted the day the streams come from Railcam directly
rather than through YouTube — which is the fix that actually lasts.

## Costs, revised

- **Compute** — nothing while the VM is stopped. The boot disk is about
  £1/month. Starting it is `watcher_running = true` and an apply.
- **Storage** — 2.34 GB up as of 1/9, a few pence a month. Lifecycle rules
  cool to Nearline at 14 days, Coldline at 45, delete at 90.
- **Firestore** — free, and now genuinely so. The upload rewrote all 549
  documents every run, which at a fifteen minute cadence is about 52,000
  writes a day against a free tier of 20,000. It now writes only what
  changed: a run with nothing new costs one heartbeat.

## Not yet solved

**Ask Railcam for direct access.** The proper fix for the finding above,
and the one that removes yt-dlp, the player challenge and the IP question
in a single stroke. Everything else here is a way of working around not
having it.

**The annotator's save endpoint is dev-server only.** It runs as a Vite plugin
(`apply: 'serve'`), so a built deployment gets a read-only annotator. Either
the control room runs from the VM with a small server, or the endpoint moves
somewhere it can live in production. This needs deciding before the app is
deployed rather than after.

**Where the control room runs.** Firebase Hosting is free and would serve the
public timetable happily, but the annotator problem above means the operator
side probably wants to sit on the VM. One app on one host stays the goal.

**Node on the VM is 18.20.4**, too old for yt-dlp's JS runtime, so it warns
on every resolve. Harmless while the manifest still resolves and worth
fixing before it is not.

## Done

- Frame buffers consolidated onto the ring.
- Project created, Terraform applied, secrets in Secret Manager.
- Site deployed and auto-deploying; GitHub Pages retired.
- Stills and clips served from the private bucket, gated on the operator
  grant — the observations are public, the footage is Railcam's.
- Uploads and classification on a timer, writing only what changed.

## Order of work

1. Ask Railcam for direct stream access. Everything below is smaller.
2. Wire `visit.py` — 97% of detections still report direction as unclear.
3. Move the watcher onto the fine-tuned weights; it is still on stock COCO.
4. Solve the annotator endpoint, which is dev-server only.
5. Verify detections by hand. One of 544 so far.

## Files

- `terraform/main.tf` — VM, bucket, service account, NAT, firewall
- `terraform/variables.tf` — sizing and retention, no money-spending defaults
- `terraform/startup.sh` — provisioning and the systemd timer that starts the
  watcher at the hour the line does
