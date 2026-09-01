# Letting GitHub Actions deploy, without a key to leak.
#
# The usual way is a service account key downloaded as JSON and pasted into a
# repository secret, where it sits for years, works from anywhere, and is
# still valid long after whoever added it has moved on. Workload Identity
# Federation avoids that: GitHub signs a short-lived token saying which
# repository and which workflow is running, Google trusts that signature, and
# nothing downloadable exists at all.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "Deploys the site from dr-harper/west_somerset_railway"

  depends_on = [time_sleep.apis_settle]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # Without this a token from any repository on GitHub would be accepted.
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "wsr-site-deployer"
  display_name = "Deploys the site from CI"
  description  = "Firebase Hosting only. It cannot read detections or touch the machine."
}

# Only what deploying needs. It cannot read Firestore, cannot reach the
# captures, cannot see the secret, and cannot restart the watcher.
resource "google_project_iam_member" "deployer_hosting" {
  project = var.project_id
  role    = "roles/firebasehosting.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_from_github" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

output "github_workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "github_deployer_service_account" {
  value = google_service_account.deployer.email
}
