# The model LocalAI mounts as an image volume. The model-images workflow builds and pushes
# TAG when this file changes on main, and never rebuilds a tag that already exists.
#
# To change the model, update REPO, REVISION, FILE, SHA256 and TAG together. TAG is the
# quantization and the first seven characters of REVISION.
ARG FILE=Qwen3.5-4B-Q4_K_M.gguf
ARG TAG=q4_k_m-e87f176

FROM alpine:3.24 AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
ARG REPO=unsloth/Qwen3.5-4B-GGUF
ARG REVISION=e87f176479d0855a907a41277aca2f8ee7a09523
ARG SHA256=00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4
ARG FILE
RUN wget -q -O /model.gguf "https://huggingface.co/${REPO}/resolve/${REVISION}/${FILE}" \
  && echo "${SHA256}  /model.gguf" | sha256sum -c

FROM scratch
ARG FILE
ARG TAG
LABEL org.opencontainers.image.source="https://github.com/jrmatherly/home-cluster" \
  org.opencontainers.image.description="Qwen3.5-4B Q4_K_M GGUF for LocalAI" \
  org.opencontainers.image.licenses="Apache-2.0" \
  org.opencontainers.image.version="${TAG}"
COPY --from=fetch /model.gguf /${FILE}
