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

# Derived from what is actually deployed rather than written out by hand: the
# machine dropped from e2-medium to e2-small and this string went on claiming
# the old one, which is how an estimate quietly becomes wrong.
locals {
  compute_estimate = {
    "e2-micro"  = "~£5-6"
    "e2-small"  = "~£9-11"
    "e2-medium" = "~£18-22"
  }
}

output "monthly_estimate" {
  description = "Rough, and worth checking against the calculator."
  value = join(" ", [
    "compute ${lookup(local.compute_estimate, var.machine_type, "?")}",
    "(${var.machine_type}, always on)",
    "+ storage ~£1-6 growing + Firestore £0 (free tier)",
  ])
}
