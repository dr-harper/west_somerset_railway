# The project already exists on the personal account, billed to
# "Personal Billing Account" (013666-028EB6-59579B).
project_id = "west-somerset-railway-project"
region     = "europe-west2"
zone       = "europe-west2-a"

# The frame buffers are consolidated onto the ring now, so the footprint is
# ~1.2GB and flat: 479MB of model and interpreter, plus a bounded ring.
# e2-micro (1GB) becomes possible once the H.264 segment buffer lands and
# takes the ring from 0.7GB to under 10MB.
machine_type = "e2-small"
