# The captures bucket, registered with Firebase so the browser can read it.
#
# The bucket already exists in main.tf and the watcher writes to it with a
# service account. That is enough for the pipeline and not enough for the
# control room: a browser has no service account, and the operator tools
# were showing broken images because every still resolved to a path that
# only exists on the laptop that recorded it.
#
# Registering it with Firebase Storage lets the web SDK fetch objects using
# the signed-in user's own token, checked against storage.rules. The bucket
# itself stays private — no public access, no signed URLs to leak.

resource "google_firebase_storage_bucket" "captures" {
  provider  = google-beta
  project   = var.project_id
  bucket_id = google_storage_bucket.captures.name

  depends_on = [google_firebase_project.main]
}

resource "google_firebaserules_ruleset" "storage" {
  project = var.project_id

  source {
    files {
      name    = "storage.rules"
      content = file("${path.module}/../../storage.rules")
    }
  }

  depends_on = [google_firebase_storage_bucket.captures]
}

resource "google_firebaserules_release" "storage" {
  provider = google-beta
  project  = var.project_id

  # Storage releases are named for the bucket they govern, unlike Firestore's
  # single "cloud.firestore". Getting this wrong deploys a ruleset that binds
  # to nothing and leaves the previous rules live.
  name         = "firebase.storage/${google_storage_bucket.captures.name}"
  ruleset_name = google_firebaserules_ruleset.storage.name

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.storage]
  }
}
