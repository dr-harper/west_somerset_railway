# Secrets live in Secret Manager, not in files on the machine.
#
# The Gemini key currently sits in train_detection/.env at mode 600 and
# gitignored, which works until an image is built from the directory or a
# backup copies it. An earlier key reached git history and had to be burned;
# the point of this is that there is nothing on disk to leak.
#
# Terraform creates the container and the access, never the value. A secret
# in a Terraform variable ends up in state, and state is a file like any
# other.

resource "google_secret_manager_secret" "gemini_key" {
  project   = var.project_id
  secret_id = "gemini-api-key"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    system = "wsr-monitor"
  }

  depends_on = [google_project_service.needed]
}

# The machine may read the current value and nothing else: not write it, not
# list other secrets, not see earlier versions it has no use for.
resource "google_secret_manager_secret_iam_member" "watcher_reads_gemini" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.gemini_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.watcher.email}"
}

output "add_the_secret_value" {
  description = "Run this once; the value never passes through Terraform."
  value = join(" ", [
    "gcloud secrets versions add ${google_secret_manager_secret.gemini_key.secret_id}",
    "--project=${var.project_id}",
    "--data-file=<(grep -h '^GEMINI_API_KEY=' train_detection/.env | cut -d= -f2-)",
  ])
}
