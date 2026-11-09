# PR-P2 verification

Commands and pass conditions for routing the career-ops web pod through CLIProxyAPI. The operator
runs every cluster step; no agent runs `kubectl`. Nothing below is a result. Screenshots go under
`private/review/`. The career-ops client key (the `api_key` in `[cliproxyapi]`, or a second key
minted in the manager console) is never pasted into a command, only read from a Secret.

## Unit

| Check                                                                                                      | Pass condition                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run --locked pytest template/scripts/test_validate.py -q`                                              | all pass, the six `career_ops` proxy tests included                                                                                                               |
| `bash .claude/plans/2026-11-07-career-ops-deploy/render-check.sh .github/template-tests/valid/public.toml` | render and `oxfmt --check` pass; the career-ops Secret and env match a render from `main`                                                                         |
| The same script on a copy of `public.toml` carrying the proxy pair and no `claude_oauth_token`             | Secret has `ANTHROPIC_AUTH_TOKEN` and no `CLAUDE_CODE_OAUTH_TOKEN`; env has `ANTHROPIC_BASE_URL`; the proxy NetworkPolicy has one `from` item with both selectors |
| `just configure` on the real config (pair set), then `git status --porcelain`                              | the diff touches only the career-ops HelmRelease and Secret and the proxy NetworkPolicy; the other re-encrypted sops files are restored                           |

## Build

Run these before the real pod switches. The scratch pod carries the web pod's labels so the proxy's
NetworkPolicy admits it, and reads the key from a Secret, never from a shell argument.

1. Create the scratch Secret. `read -rs` takes the key from the terminal without echo or history:

    ```sh
    read -rs k && kubectl -n career-ops create secret generic p2-scratch --from-literal=ANTHROPIC_AUTH_TOKEN="$k"; unset k
    ```

2. Apply the scratch pod. The career-ops namespace enforces `restricted`, so the pod needs the same
   security context as the web pod:

    ```sh
    kubectl -n career-ops apply -f - <<'YAML'
    apiVersion: v1
    kind: Pod
    metadata:
      name: p2-scratch
      labels:
        app.kubernetes.io/name: career-ops
        app.kubernetes.io/controller: web
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: app
          image: ghcr.io/jrmatherly/career-ops-server:latest
          command: ["sleep", "3600"]
          env:
            - name: ANTHROPIC_BASE_URL
              value: http://cliproxyapi.llms.svc.cluster.local:8317
            - name: ANTHROPIC_AUTH_TOKEN
              valueFrom:
                secretKeyRef: { name: p2-scratch, key: ANTHROPIC_AUTH_TOKEN }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          volumeMounts:
            - { name: home, mountPath: /home/app }
            - { name: tmp, mountPath: /tmp }
      volumes:
        - { name: home, emptyDir: {} }
        - { name: tmp, emptyDir: {} }
    YAML
    kubectl -n career-ops wait --for=condition=Ready pod/p2-scratch --timeout=120s
    ```

3. One request through the proxy:

    ```sh
    kubectl -n career-ops exec p2-scratch -- claude -p "Reply with the single word ok" --tools "" --disallowedTools "*"
    ```

    Pass when it prints `ok`, and when `env | grep -c CLAUDE_CODE_OAUTH_TOKEN` in the pod prints 0.

4. The forced 429. In the manager console, disable every seat the career-ops key can use for a
   minute, run step 3 again, and copy the exact stderr line into Appendix C of
   `/Users/jason/dev/career-ops/docs/superpowers/plans/2026-11-08-scan-automation-and-platform.md`.
   The drain's batch-stop rule (`/quota|rate limit/i`, `/usage limit reached/i`) is matched against
   that line; if it does not match, the regex gains the proxy's wording in career-ops. Re-enable the
   seats.

5. The switch. With `anthropic_base_url` and `anthropic_auth_token` set under `[career_ops]` and
   `claude_oauth_token` removed, so no run carries both:

    ```sh
    just configure
    git status --porcelain
    ```

    Pass when the diff touches only `kubernetes/apps/career-ops/career-ops/app/helmrelease.yaml`,
    `.../secret.sops.yaml` and `kubernetes/apps/llms/cliproxyapi/app/networkpolicy.yaml`. Restore the
    other re-encrypted sops files with the three-glob `git checkout` the recipe prints, commit, push,
    and watch Flux roll the web pod (reloader restarts it on the Secret change).

6. Clean up: `kubectl -n career-ops delete pod p2-scratch secret p2-scratch`.

## Live lanes

Each lane at the PR head, after the switch in Build step 5.

| Lane | Command                                                                                                                                                                            | Pass condition                                                                                                                                               | Screenshot               |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| 1    | One dashboard evaluate at trunk (OAuth token, before the switch) and one at head (proxy) on the same fixture URL                                                                   | both produce a report with the same sections                                                                                                                 | `p2-evaluate-parity.png` |
| 2    | Build step 3 in the scratch pod                                                                                                                                                    | prints `ok`                                                                                                                                                  | `p2-scratch-ok.png`      |
| 3    | The manager console's usage page right after lane 2                                                                                                                                | the request appears under the career-ops key                                                                                                                 | `p2-usage.png`           |
| 4    | `kubectl -n career-ops exec deploy/career-ops -- node /app/doctor.mjs`                                                                                                             | the gateway line prints with the proxy URL                                                                                                                   | `p2-doctor.png`          |
| 5    | `kubectl -n career-ops exec deploy/career-ops -- sh -c 'env \| grep -c CLAUDE_CODE_OAUTH_TOKEN'`                                                                                   | prints 0 (grep exits 1, which is the pass)                                                                                                                   | `p2-no-oauth.png`        |
| 6    | `kubectl -n default run p2-deny --rm -i --restart=Never --image=curlimages/curl -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' http://cliproxyapi.llms.svc.cluster.local:8317/` | curl exits 28 (timeout), no HTTP status                                                                                                                      | `p2-netpol-deny.png`     |
| 7    | `kubectl -n career-ops exec deploy/career-ops -- node -e 'fetch("http://cliproxyapi.llms.svc.cluster.local:8317/").then(r=>console.log(r.status))'`                                | prints an HTTP status, so the policy admits the web pod. The plan names `/healthz` and 200; the proxy's health path is unverified here, so any status passes | `p2-netpol-allow.png`    |
| 8    | Build step 4                                                                                                                                                                       | the stderr line is in Appendix C and matches, or was added to, the drain's limit regexes                                                                     | `p2-429.png`             |
| 9    | Restore `claude_oauth_token` in the config, remove the pair, `just configure`, `git diff --stat kubernetes/`                                                                       | the diff restores the OAuth-only manifests and removes the proxy's `from` item; then switch back and restore the sops churn                                  | `p2-render-off.png`      |
| 10   | Build steps 1 to 3 with the scratch Secret holding a wrong key                                                                                                                     | `claude -p` fails fast with an authentication error (401 or 403 wording) the dashboard's fatal-stderr rule would catch                                       | `p2-bad-key.png`         |

## Perf

| Item     | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Metric   | time to first streamed token of a dashboard evaluate, OAuth token at trunk and proxy at head |
| Probe    | three evaluates each on the same fixture URL, interleaved, read from the run log timestamps  |
| Baseline | the trunk median, recorded first                                                             |
| Rule     | head within 2 seconds of trunk                                                               |

## Review gate

Copy the lane 2 and lane 3 screenshots to `private/review/p2-review-ok.png` and
`private/review/p2-review-usage.png`, record 30 to 60 seconds of one dashboard evaluate through the
proxy as `private/review/p2-review.mp4`, post them in chat, and stop at merge-ready.
