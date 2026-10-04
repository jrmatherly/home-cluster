# The model llama-server mounts as an image volume. The model-images workflow builds and pushes
# TAG when this file changes on main, and never rebuilds a tag that already exists.
#
# To change the model, update REPO, REVISION, FILE, SHA256 and TAG together. TAG is the
# quantization and the first seven characters of REVISION.
ARG FILE=Phi-4-mini-instruct-Q4_K_M.gguf
ARG TAG=q4_k_m-78eb92a

FROM alpine:3.24 AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
ARG REPO=unsloth/Phi-4-mini-instruct-GGUF
ARG REVISION=78eb92a46fc37e6b524df991ed9aca9bc6aa7b80
ARG SHA256=88c00229914083cd112853aab84ed51b87bdf6b9ce42f532d8c85c7c63b1730a
ARG FILE
RUN wget -q -O /model.gguf "https://huggingface.co/${REPO}/resolve/${REVISION}/${FILE}" \
  && echo "${SHA256}  /model.gguf" | sha256sum -c

FROM scratch
ARG FILE
ARG TAG
LABEL org.opencontainers.image.source="https://github.com/jrmatherly/home-cluster" \
  org.opencontainers.image.description="Phi-4-mini-instruct Q4_K_M GGUF for llama-server" \
  org.opencontainers.image.licenses="MIT" \
  org.opencontainers.image.version="${TAG}"
COPY --from=fetch /model.gguf /${FILE}
