---
paths:
    - "images/**"
    - ".github/workflows/model-images.yaml"
---

# Model images

- `images/<model>/Dockerfile` is the recipe for a model image that LocalAI mounts as an image volume. It downloads the GGUF from Hugging Face at a pinned `REVISION`, checks `SHA256`, and copies it into a `scratch` image. The Model Images workflow (`.github/workflows/model-images.yaml`) builds and pushes it to `ghcr.io/jrmatherly/models/<model>` when `images/**` changes on `main`, and never rebuilds a tag that exists. When the pin changes, update `REPO`, `REVISION`, `FILE`, `SHA256` and `TAG` (`<quant>-<first 7 chars of REVISION>`) together, then put the digest from the run summary in the HelmRelease, and make the new GHCR package public after its first push, because the kubelet pulls it with no pull secret.
