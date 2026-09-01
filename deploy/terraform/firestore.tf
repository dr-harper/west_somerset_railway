# Firestore, and the rules that decide who may change a verification.
#
# The database is Native mode in the same region as everything else. Rules
# are deployed from the repo rather than the console, so what is live is
# whatever is in version control — a rule changed by hand in a console is a
# rule nobody can review.

resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # The detections are the record of what ran on the railway. Losing them to
  # a mistyped delete is not recoverable from anywhere else.
  delete_protection_state = "DELETE_PROTECTION_ENABLED"

  depends_on = [time_sleep.apis_settle]
}

resource "google_firebaserules_ruleset" "firestore" {
  project = var.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../../firestore.rules")
    }
  }

  depends_on = [google_firestore_database.main]
}

resource "google_firebaserules_release" "firestore" {
  provider     = google-beta
  project      = var.project_id
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }
}
