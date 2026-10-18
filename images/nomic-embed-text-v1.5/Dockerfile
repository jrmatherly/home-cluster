# The embedding model LocalAI mounts as an image volume. The model-images workflow builds
# and pushes TAG when this file changes on main, and never rebuilds a tag that already exists.
#
# To change the model, update REPO, REVISION, FILE, SHA256 and TAG together. TAG is the
# quantization and the first seven characters of REVISION.
ARG FILE=nomic-embed-text-v1.5.Q8_0.gguf
ARG TAG=q8_0-0188c9b

FROM alpine:3.24 AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
ARG REPO=nomic-ai/nomic-embed-text-v1.5-GGUF
ARG REVISION=0188c9bf409793f810680a5a431e7b899c46104c
ARG SHA256=3e24342164b3d94991ba9692fdc0dd08e3fd7362e0aacc396a9a5c54a544c3b7
ARG FILE
RUN wget -q -O /model.gguf "https://huggingface.co/${REPO}/resolve/${REVISION}/${FILE}" \
  && echo "${SHA256}  /model.gguf" | sha256sum -c

FROM scratch
ARG FILE
ARG TAG
LABEL org.opencontainers.image.source="https://github.com/jrmatherly/home-cluster" \
  org.opencontainers.image.description="nomic-embed-text-v1.5 Q8_0 GGUF for LocalAI" \
  org.opencontainers.image.licenses="Apache-2.0" \
  org.opencontainers.image.version="${TAG}"
COPY --from=fetch /model.gguf /${FILE}
