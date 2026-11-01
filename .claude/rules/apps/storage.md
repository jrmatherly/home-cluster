---
paths:
    - "template/config/kubernetes/apps/storage/**"
    - "kubernetes/apps/storage/**"
---

# Storage

- `storage/local-path-provisioner` provides the default StorageClass `local-path`. Its volumes are directories under `/var/mnt/local-path`, declared as a Talos `UserVolumeConfig` in `talos/all/72-volumes.yaml`, so each volume is pinned to one node and has no size limit.
