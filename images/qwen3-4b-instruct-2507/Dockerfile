# The model llama-server mounts as an image volume. The model-images workflow builds and pushes
# TAG when this file changes on main, and never rebuilds a tag that already exists.
#
# To change the model, update REPO, REVISION, FILE, SHA256 and TAG together. TAG is the
# quantization and the first seven characters of REVISION.
ARG FILE=Qwen3-4B-Instruct-2507-Q4_K_M.gguf
ARG TAG=q4_k_m-a06e946

FROM alpine:3.24 AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
ARG REPO=unsloth/Qwen3-4B-Instruct-2507-GGUF
ARG REVISION=a06e946bb6b655725eafa393f4a9745d460374c9
ARG SHA256=3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597
ARG FILE
RUN wget -q -O /model.gguf "https://huggingface.co/${REPO}/resolve/${REVISION}/${FILE}" \
  && echo "${SHA256}  /model.gguf" | sha256sum -c

FROM scratch
ARG FILE
ARG TAG
LABEL org.opencontainers.image.source="https://github.com/jrmatherly/home-cluster" \
  org.opencontainers.image.description="Qwen3-4B-Instruct-2507 Q4_K_M GGUF for llama-server" \
  org.opencontainers.image.licenses="Apache-2.0" \
  org.opencontainers.image.version="${TAG}"
COPY --from=fetch /model.gguf /${FILE}
