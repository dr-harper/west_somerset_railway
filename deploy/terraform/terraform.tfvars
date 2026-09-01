# The project already exists on the personal account, billed to
# "Personal Billing Account" (013666-028EB6-59579B).
project_id = "west-somerset-railway-project"
region     = "europe-west2"
zone       = "europe-west2-a"

# 4GB while the watcher still holds raw frames in memory. Drops to e2-small
# once the frame buffers are consolidated onto the ring.
machine_type = "e2-medium"
