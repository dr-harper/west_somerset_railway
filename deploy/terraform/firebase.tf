# The Firebase layer, on top of the GCP project.
#
# Firestore is a GCP product and worked the moment it was created. Auth and
# Hosting are not: they need the project registered with Firebase, which is a
# separate step that is easy to miss precisely because the database already
# works without it. Setting the site's project id before this exists gives a
# page that reads detections happily and offers a sign-in button that cannot
# succeed.

resource "google_firebase_project" "main" {
  provider = google-beta
  project  = var.project_id

  depends_on = [time_sleep.apis_settle]
}

# The web app's own identity. Its config is what the site is built with, so
# it is read back as an output rather than copied out of a console by hand.
resource "google_firebase_web_app" "site" {
  provider     = google-beta
  project      = var.project_id
  display_name = "West Somerset Railway Timetables"

  # Removing the app should not silently orphan a site that is still using it.
  deletion_policy = "DELETE"

  depends_on = [google_firebase_project.main]
}

data "google_firebase_web_app_config" "site" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.site.app_id
  project    = var.project_id
}

# Identity Platform is what Firebase Auth is built on. Enabling it here means
# the sign-in gate on the control room has something to talk to.
resource "google_identity_platform_config" "auth" {
  provider = google-beta
  project  = var.project_id

  depends_on = [google_firebase_project.main]
}

output "firebase_web_config" {
  description = "What the site is built with. The api key is not a secret: it identifies the project and authorises nothing, which the security rules do."
  value = {
    project_id  = var.project_id
    app_id      = google_firebase_web_app.site.app_id
    api_key     = data.google_firebase_web_app_config.site.api_key
    auth_domain = data.google_firebase_web_app_config.site.auth_domain
  }
  sensitive = false
}
