# Nothing here has a default that spends money by accident: the project and
# the billing account must both be named explicitly.

variable "project_id" {
  description = "The GCP project this lives in. Its own project, not a shared one."
  type        = string
}

variable "region" {
  description = "London: nearest to the railway, and where the existing gcloud config points."
  type        = string
  default     = "europe-west2"
}

variable "zone" {
  type    = string
  default = "europe-west2-a"
}

variable "machine_type" {
  description = <<-EOT
    Measured need is 0.52 vCPU and 2GB, on an M-series Mac. A cloud vCPU is
    slower, so 1 vCPU is the working figure.

    e2-medium (1-2 vCPU, 4GB) until the frame buffers are consolidated —
    the watcher holds raw frames today and sits at 2GB. Once that lands,
    e2-small (2GB) is enough and roughly halves the bill.
  EOT
  type        = string
  default     = "e2-medium"
}

variable "capture_retention_days" {
  description = <<-EOT
    Captures accumulate at about 27.5GB a month. Roughly two thirds of that
    is video of a stationary train, which the arrival/dwell/departure work
    removes at source; until then, age them out.
  EOT
  type        = number
  default     = 90
}

variable "watcher_start_hour" {
  description = "Local hour the line starts running."
  type        = number
  default     = 8
}

variable "watcher_hours" {
  type    = number
  default = 11
}

variable "ssh_source_ranges" {
  description = "Who may reach SSH. Left empty, only IAP can, which is the intent."
  type        = list(string)
  default     = []
}

variable "github_repository" {
  description = "owner/repo allowed to deploy. Narrow on purpose: without it, a token from any repository on GitHub would be accepted."
  type        = string
  default     = "dr-harper/west_somerset_railway"
}
