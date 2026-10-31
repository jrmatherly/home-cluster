# syntax=docker/dockerfile:1
# Lints, scrubs and builds the docs site into an nginx image. Build from the
# repository root and hand it the git directory, which is where each page's
# "Last updated" date comes from, and the private denylist for the scrub:
#   docker build --build-context gitdir=.git \
#     --secret id=scrub_denylist,src=private/scrub-denylist.txt -t home-cluster-docs docs
# Both are required: a build that cannot read the history or the denylist
# fails instead of shipping pages without dates or without the scrub.

FROM scratch AS gitdir

FROM node:24-alpine@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85 AS build
RUN apk add --no-cache git bash
WORKDIR /repo/docs
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
# The scrub reads the denylist only when the secret is given; CI passes it
# from a repository secret, a local build from private/.
RUN --mount=type=secret,id=scrub_denylist,required=true \
    SCRUB_DENYLIST=/run/secrets/scrub_denylist ./scrub-check.sh
# The mounted .git belongs to another uid, which git refuses without
# safe.directory. A shallow clone would leave every page without a date, and
# nimbus-docs only warns, so both stop the build here. The lint runs after the
# build, because nimbus-docs 0.16 and later read the rule set from the
# .nimbus/lint.json that only a build writes.
RUN --mount=type=bind,from=gitdir,target=/repo/.git \
    set -eu; \
    git config --global --add safe.directory /repo; \
    git rev-parse --git-dir >/dev/null; \
    if [ "$(git rev-parse --is-shallow-repository)" = true ]; then \
      echo "Shallow clone: fetch full history (fetch-depth: 0), or pages lose their dates." >&2; exit 1; \
    fi; \
    npm run build; \
    [ -f dist/index.html ] || { echo "No pages were built." >&2; exit 1; }; \
    npm run lint:docs; \
    npm run typecheck; \
    undated=$(find dist -name index.html -exec grep -L '<time datetime=' {} + || true); \
    if [ -n "$undated" ]; then \
      echo "Pages without a Last updated date (not committed, or the history is unreadable):" >&2; \
      echo "$undated" >&2; exit 1; \
    fi

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
# Links the GHCR package to the repository, so it shows up on the repository page.
LABEL org.opencontainers.image.source=https://github.com/jrmatherly/home-cluster
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/docs/dist /usr/share/nginx/html
