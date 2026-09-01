output "instance_name" {
  value = google_compute_instance.watcher.name
}

output "captures_bucket" {
  value       = google_storage_bucket.captures.name
  description = "Where clips and stills go. Not Firestore — that holds only the records."
}

output "ssh_command" {
  description = "Over IAP, so the machine needs no public SSH port."
  value       = "gcloud compute ssh ${google_compute_instance.watcher.name} --zone ${var.zone} --tunnel-through-iap --project ${var.project_id}"
}

output "monthly_estimate" {
  description = "Rough, and worth checking against the calculator before applying."
  value       = "compute ~£18-22 (e2-medium, always on) + storage ~£1-6 growing + Firestore £0 (free tier)"
}
