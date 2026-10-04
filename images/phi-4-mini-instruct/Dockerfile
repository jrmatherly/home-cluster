# The model llama-server mounts as an image volume. Build and push by hand when the pin changes:
#
#   docker build --platform linux/amd64 -t ghcr.io/jrmatherly/models/phi-4-mini-instruct:q4_k_m-78eb92a .
#   docker push ghcr.io/jrmatherly/models/phi-4-mini-instruct:q4_k_m-78eb92a
#
# The tag is the quantization and the first seven characters of REVISION.
FROM alpine:3.22 AS fetch
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
ARG REPO=unsloth/Phi-4-mini-instruct-GGUF
ARG REVISION=78eb92a46fc37e6b524df991ed9aca9bc6aa7b80
ARG FILE=Phi-4-mini-instruct-Q4_K_M.gguf
ARG SHA256=88c00229914083cd112853aab84ed51b87bdf6b9ce42f532d8c85c7c63b1730a
RUN wget -q -O /model.gguf "https://huggingface.co/${REPO}/resolve/${REVISION}/${FILE}" \
  && echo "${SHA256}  /model.gguf" | sha256sum -c

FROM scratch
LABEL org.opencontainers.image.source="https://github.com/jrmatherly/home-cluster" \
  org.opencontainers.image.description="Phi-4-mini-instruct Q4_K_M GGUF for llama-server" \
  org.opencontainers.image.licenses="MIT"
COPY --from=fetch /model.gguf /Phi-4-mini-instruct-Q4_K_M.gguf
