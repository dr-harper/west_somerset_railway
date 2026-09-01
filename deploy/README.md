# Deploying the monitor

Notes for moving the railway monitor off a laptop and onto a machine that is
awake when the line is. Written 31 August 2026.

## Why

The monitor currently runs on a MacBook. That has cost two mornings already
— a scheduled job that failed silently, and a network change that pointed the
control room at a machine that no longer existed — and it stops entirely
whenever the laptop is shut. A gala day missed is not recoverable.

## Before anything is created

**The active gcloud account is the wrong one.** As of writing:

```
account = michael@heatgeek.com
project = skoon-zor-dev
```

That is the work account. This project belongs on the personal one
(`mikeylharper@gmail.com`, already authenticated but not active). Nothing in
`terraform/` has been applied, deliberately.

Switching accounts and creating the project are yours to do:

```bash
gcloud config set account mikeylharper@gmail.com
gcloud projects create wsr-monitor --name="WSR Monitor"
gcloud billing projects link wsr-monitor --billing-account=<personal billing id>
gcloud config set project wsr-monitor
```

The project is made by hand rather than in Terraform on purpose. Creating
projects needs an org or folder and a billing account, and doing it from code
makes it far too easy to attach the wrong billing account to the right
project.

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

One small always-on VM, one bucket, Firestore. No public IP: egress goes
through Cloud NAT and SSH arrives over IAP, so nothing is exposed.

Deliberately dull. This is a monitor that has to be up in the morning, not
something that needs to scale.

## Not yet solved

**The annotator's save endpoint is dev-server only.** It runs as a Vite plugin
(`apply: 'serve'`), so a built deployment gets a read-only annotator. Either
the control room runs from the VM with a small server, or the endpoint moves
somewhere it can live in production. This needs deciding before the app is
deployed rather than after.

**Where the control room runs.** Firebase Hosting is free and would serve the
public timetable happily, but the annotator problem above means the operator
side probably wants to sit on the VM. One app on one host stays the goal.

**Secrets.** The Gemini key currently lives in `train_detection/.env`,
gitignored, mode 600. On the VM it should be Secret Manager, not a file baked
into an image.

**Uploads are manual.** `upload_episodes.py` runs when someone remembers, so
the control room is routinely hours behind. On the VM it should be a timer,
and it should write only what changed rather than rewriting the day.

**The classifier is manual too**, and last ran on 30 August. Same fix.

## Order of work

1. Consolidate the frame buffers onto the ring — biggest single saving, and it
   decides the machine size.
2. Create the project on the personal account, apply the Terraform, get the
   watcher running on the VM alongside the laptop for a day to compare.
3. Move uploads and classification onto timers on the VM.
4. Decide where the control room lives and solve the annotator endpoint.
5. Retire the laptop run.

## Files

- `terraform/main.tf` — VM, bucket, service account, NAT, firewall
- `terraform/variables.tf` — sizing and retention, no money-spending defaults
- `terraform/startup.sh` — provisioning and the systemd timer that starts the
  watcher at the hour the line does
