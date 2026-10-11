import { expect, mock, test } from "claude-code/testing";
import type { Engine } from "claude-code/testing";
import type { On } from "claude-code";

const at = (h: number, m: number) => new Date(2026, 9, 10, h, m).getTime();
function world(on: On, porcelain = "", now = at(10, 0)) {
  const status: unknown[] = [];
  const toasts: unknown[] = [];
  const runs: unknown[] = [];
  mock.clock(on, { now });
  on("tool.call", () => ({ result: "ran" }));
  on("session.cwd", () => ({ value: "/work" }));
  on("process.run", ($, e) => {
    runs.push(e.argv);
    return {
      value: {
        exitCode: 0,
        stdout: porcelain,
        stderr: "",
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    };
  });
  on("ui.status", ($, e) => {
    status.push(e.text);
    return { value: undefined };
  });
  on("ui.toast", ($, e) => {
    toasts.push(e.text);
    return { value: undefined };
  });
  return { status, toasts, runs };
}
const bash = ($: Engine, command: string) => $.tool.call({ tool: "Bash", command });
const denied = async ($: Engine, commands: string[], reason: RegExp) => {
  for (const command of commands) expect(String((await bash($, command)).deny)).toMatch(reason);
};
const allowed = async ($: Engine, commands: string[]) => {
  for (const command of commands) expect((await bash($, command)).deny).toBeUndefined();
};

test("node maintenance is refused inside the UniFi window", async ($, on) => {
  world(on, "", at(3, 0));
  await denied(
    $,
    [
      "just talos drain k8s-cp-2",
      "just talos apply",
      "talosctl -n 192.168.22.22 reboot",
      "topf upgrade",
      "kubectl drain k8s-cp-2 --ignore-daemonsets",
    ],
    /02:45 to 03:30/,
  );
});
test("node maintenance runs outside the window", async ($, on) => {
  world(on);
  await allowed($, ["just talos drain k8s-cp-2", "talosctl -n 192.168.22.22 reboot"]);
});
test("a secrets file is readable only through the listed parsers, per command segment", async ($, on) => {
  world(on);
  await denied(
    $,
    [
      "cat cluster.toml | head",
      "grep -n endpoint cluster.toml",
      'python3 -c "import tomllib" cluster.toml',
      "cp age.key /tmp/x",
      "cat kubeconfig | head -30",
      "cat cluster.toml; just template doctor",
      "cp age.key /tmp/x && taplo check x.toml",
    ],
    /names a secrets file/,
  );
  await allowed($, [
    "uv run --locked --no-dev template/scripts/validate.py cluster.toml",
    "just template check-layout",
    'taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml',
    'git commit -m "feat(template): keep cluster.toml in the sample layout"',
    'grep -rn "cluster\\.toml" template/ CLAUDE.md',
    "git status --short",
  ]);
});
test("writing a rendered file is refused with the source hint", async ($, on) => {
  world(on);
  const edit = await $.tool.call({
    tool: "Edit",
    file_path: "/Users/jason/dev/home-cluster/kubernetes/apps/media/sonarr/app/helmrelease.yaml",
    old_string: "a",
    new_string: "b",
  });
  expect(String(edit.deny)).toMatch(/template\/config/);
  const worktree = await $.tool.call({
    tool: "Write",
    file_path: "/work/talos/all/99.yaml",
    content: "x",
  });
  expect(String(worktree.deny)).toMatch(/template\/config/);
  const source = await $.tool.call({
    tool: "Edit",
    file_path:
      "/Users/jason/dev/home-cluster/template/config/kubernetes/apps/media/sonarr/app/helmrelease.yaml.j2",
    old_string: "a",
    new_string: "b",
  });
  expect(source.deny).toBeUndefined();
  await denied(
    $,
    [
      "echo x > ./talos/all/99.yaml",
      "cat a >> kubernetes/apps/x.yaml",
      "sd 'replicas: 1' 'replicas: 2' kubernetes/apps/media/sonarr/app/helmrelease.yaml",
      "cat x | tee bootstrap/helmfile/apps.yaml",
      "cat a | tee -a /Users/jason/dev/home-cluster/talos/all/1.yaml",
      "sed -i 's/a/b/' /Users/jason/dev/home-cluster/talos/all/10.yaml",
      "cp /tmp/x.yaml kubernetes/apps/x.yaml",
      "mv a.yaml bootstrap/helmfile/apps.yaml",
      "yq -i '.a=1' kubernetes/apps/x.yaml",
      "sops -e -i kubernetes/apps/x.sops.yaml",
      "echo x >kubernetes/apps/x.yaml",
      "echo x >>talos/all/1.yaml",
      "cp a.yaml kubernetes/apps/x.yaml 2>/dev/null",
      "cp a.yaml kubernetes/apps/x.yaml # note",
      "cat a | tee /tmp/a kubernetes/apps/x.yaml",
      "mv kubernetes/apps/x.yaml /tmp/",
      'echo x > "kubernetes/apps/x.yaml"',
      "cp a 'talos/all/1.yaml'",
      "echo x > $PWD/kubernetes/apps/x.yaml",
      "echo x > /work/talos/all/99.yaml",
      "sed -Ei 's/a/b/' kubernetes/apps/x.yaml",
      "sops encrypt -i kubernetes/apps/x.sops.yaml",
      "yq --inplace '.a=1' kubernetes/apps/x.yaml",
      "perl -pi -e 's/a/b/' kubernetes/apps/x.yaml",
      "echo x > .sops.yaml",
    ],
    /writes a rendered file/,
  );
  // Reading a rendered file and sending the result elsewhere is not a write.
  await allowed($, [
    "sd 'a' 'b' template/config/kubernetes/apps/media/sonarr/app/helmrelease.yaml.j2",
    "cat kubernetes/flux/cluster/ks.yaml",
    "git diff -- kubernetes/",
    "yq '.spec.values' kubernetes/apps/x/helmrelease.yaml > /tmp/v.yaml",
    "cp kubernetes/apps/x/helmrelease.yaml /tmp/hr.yaml",
    "cat kubernetes/apps/x.yaml | tee /tmp/out",
    "helm template x chart.tgz -f <(yq . ./kubernetes/apps/x/helmrelease.yaml) > /tmp/o",
    "grep -rn foo kubernetes/ talos/",
    "cp template/config/kubernetes/a.j2 /tmp/",
    "echo x > template/config/kubernetes/apps/x.yaml.j2",
    'git commit -m "fix: kubernetes/apps/x.yaml > talos/all/1.yaml"',
    "ls kubernetes/apps 2>/dev/null",
  ]);
});
test("a commit with staged sops churn sets the pinned line and toasts", async ($, on) => {
  const seen = world(
    on,
    "M  kubernetes/apps/media/shared/app/secret.sops.yaml\nM  talos/all/10.sops.yaml\n",
  );
  await bash($, 'git commit -m "x"');
  expect(seen.runs[0]).toEqual([
    "git",
    "status",
    "--porcelain",
    "--untracked-files=no",
    "--",
    ":(top,glob)bootstrap/**/*.sops.*",
    ":(top,glob)kubernetes/**/*.sops.*",
    ":(top,glob)talos/**/*.sops.*",
  ]);
  expect(seen.status[0]).toMatch(/^2 \*\.sops\.\* files re-encrypted/);
  expect(seen.toasts[0]).toBe("committing 2 re-encrypted sops files");
});
test("git commit -a counts unstaged churn too, a plain commit does not", async ($, on) => {
  const seen = world(on, " M kubernetes/apps/media/shared/app/secret.sops.yaml\n");
  await bash($, 'git commit -m "x"');
  await bash($, 'git commit -am "x"');
  expect(seen.toasts).toEqual(["committing 1 re-encrypted sops files"]);
});
test("configure and restore refresh the pinned line; a clean tree clears it", async ($, on) => {
  const seen = world(on);
  await bash($, "just configure");
  await bash($, "git restore -- ':(glob)kubernetes/**/*.sops.*'");
  await bash($, "ls");
  expect(seen.status).toEqual([undefined, undefined]);
  expect(seen.toasts).toEqual([]);
});
