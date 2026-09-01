# Infrastructure for the West Somerset Railway monitor.
#
# One small always-on machine, one bucket, and Firestore. The measured need
# is half a vCPU and two gigabytes, so the shape is deliberately dull: this
# is a monitor that has to be up in the morning, not something that needs to
# scale.
#
# Deliberately NOT here:
#   - the project itself. Creating projects needs an org or a folder and a
#     billing account, and doing it from code makes it too easy to attach
#     the wrong one. Make the project by hand, then point this at it.
#   - anything public. The control room is reached over SSH tunnel or IAP;
#     nothing is exposed to the internet, because nothing needs to be.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # Firestore rule releases are only in the beta provider.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

# user_project_override tells Google to bill and count quota against this
# project rather than against whatever the credentials belong to. The Firebase
# Rules API refuses to work without it: a raw access token carries no quota
# project, and the call fails with SERVICE_DISABLED even though the service is
# plainly enabled — which reads as an API problem and is a credentials one.
provider "google" {
  project               = var.project_id
  region                = var.region
  zone                  = var.zone
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  zone                  = var.zone
  user_project_override = true
  billing_project       = var.project_id
}

locals {
  # One place, so the machine, the bucket and the service account are
  # obviously the same system when seen in a console.
  name = "wsr-monitor"
}

resource "google_project_service" "needed" {
  for_each = toset([
    "compute.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
    "firebaserules.googleapis.com",
    # Needed once user_project_override is on: calls are then routed through
    # this project, so this project has to be able to answer them. Without
    # these the provider reports SERVICE_DISABLED against services that are
    # visibly enabled, which sends you looking in the wrong place entirely.
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    # Firebase sits on top of the GCP project and is a separate enablement.
    # Firestore works without it, which is exactly why its absence goes
    # unnoticed until sign-in fails.
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "firebasehosting.googleapis.com",
    # Serves the stills and clips to the browser under storage.rules,
    # so the operator tools stop showing broken images while the
    # bucket itself stays private.
    "firebasestorage.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- who the machine is ----------------------------------------------------

resource "time_sleep" "apis_settle" {
  depends_on      = [google_project_service.needed]
  create_duration = "60s"
}

resource "google_service_account" "watcher" {
  account_id   = "${local.name}-vm"
  display_name = "WSR monitor VM"
  description  = "Writes captures to the bucket and episodes to Firestore. Nothing else."
}

# Deliberately narrow. The watcher creates objects and reads them back; it
# has no business deleting a bucket or touching another project's data.
resource "google_storage_bucket_iam_member" "watcher_writes_captures" {
  bucket = google_storage_bucket.captures.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.watcher.email}"
}

resource "google_project_iam_member" "watcher_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.watcher.email}"
}

resource "google_project_iam_member" "watcher_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.watcher.email}"
}

# --- where the video goes --------------------------------------------------

resource "google_storage_bucket" "captures" {
  name          = "${var.project_id}-captures"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  # Captures arrive at roughly 27.5GB a month and are looked at within days,
  # if at all. Cooling them by age is most of the storage bill.
  lifecycle_rule {
    condition { age = 14 }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition { age = 45 }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition { age = var.capture_retention_days }
    action { type = "Delete" }
  }

  versioning { enabled = false }
}

# --- the machine -----------------------------------------------------------

resource "google_compute_instance" "watcher" {
  name         = local.name
  machine_type = var.machine_type
  zone         = var.zone

  # Stopped, deliberately, and kept rather than destroyed.
  #
  # YouTube serves the HLS manifest to this machine and then refuses the
  # media: the first segment 302s to a second host which answers 403. The
  # same code against the same camera minutes apart got 490 KB on a home
  # connection and Forbidden here, on three cameras out of three. It is the
  # source address, not the code — a datacentre gets the index and not the
  # video.
  #
  # So capture runs where the address is residential and this project keeps
  # everything that does work from here: the bucket, Firestore, the secret,
  # the site. The disk is left in place because the provisioning on it is
  # sound and will be wanted the day the streams come from Railcam directly
  # rather than through YouTube.
  desired_status = var.watcher_running ? "RUNNING" : "TERMINATED"

  # It reads eleven video streams all day; losing it mid-morning to a
  # preemption would cost exactly the thing it exists to capture.
  scheduling {
    preemptible        = false
    automatic_restart  = true
    provisioning_model = "STANDARD"
  }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      # Captures stream to the bucket; the disk only holds the code, the
      # models and whatever is in flight.
      size = 30
      type = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    # No access_config block: no public IP. Egress goes through Cloud NAT,
    # and nothing can reach the machine from outside.
  }

  service_account {
    email  = google_service_account.watcher.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
    startup-script = templatefile("${path.module}/startup.sh", {
      bucket     = google_storage_bucket.captures.name
      project_id = var.project_id
      start_hour = var.watcher_start_hour
      hours      = var.watcher_hours
    })
  }

  labels = {
    system = "wsr-monitor"
  }

  depends_on = [time_sleep.apis_settle]
}

# --- getting out, and getting in ------------------------------------------

# Without a public IP the machine still has to reach YouTube, so egress goes
# through NAT.
resource "google_compute_router" "nat_router" {
  name    = "${local.name}-router"
  region  = var.region
  network = "default"
}

resource "google_compute_router_nat" "nat" {
  name                               = "${local.name}-nat"
  router                             = google_compute_router.nat_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# SSH arrives through Google's tunnel rather than from the internet, so the
# range here is IAP's, not an office address that changes.
resource "google_compute_firewall" "ssh_via_iap" {
  name    = "${local.name}-ssh-iap"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges           = length(var.ssh_source_ranges) > 0 ? var.ssh_source_ranges : ["35.235.240.0/20"]
  target_service_accounts = [google_service_account.watcher.email]
}
