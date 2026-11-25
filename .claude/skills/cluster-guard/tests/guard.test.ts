import { expect, mock, test } from "claude-code/testing";
import type { Engine } from "claude-code/testing";
import type { On } from "claude-code";

const at = (h: number, m: number) => new Date(2026, 9, 10, h, m).getTime();
function world(on: On, now = at(10, 0)) {
  mock.clock(on, { now });
  on("tool.call", () => ({ result: "ran" }));
  on("session.cwd", () => ({ value: "/work" }));
}
const bash = ($: Engine, command: string) => $.tool.call({ tool: "Bash", command });
const denied = async ($: Engine, commands: string[], reason: RegExp) => {
  for (const command of commands) expect(String((await bash($, command)).deny)).toMatch(reason);
};
const allowed = async ($: Engine, commands: string[]) => {
  for (const command of commands) expect((await bash($, command)).deny).toBeUndefined();
};

test("node maintenance is refused inside the UniFi window", async ($, on) => {
  world(on, at(3, 0));
  await denied(
    $,
    [
      "just talos drain k8s-cp-2",
      "just talos apply",
      "just talos topf apply --dry-run",
      "talosctl -n 192.0.2.22 reboot",
      "topf upgrade",
      "kubectl drain k8s-cp-2 --ignore-daemonsets",
    ],
    /02:45 to 03:30/,
  );
});
test("node maintenance runs outside the window", async ($, on) => {
  world(on);
  await allowed($, ["just talos drain k8s-cp-2", "talosctl -n 192.0.2.22 reboot"]);
});
for (const [h, m, open] of [
  [2, 44, true],
  [2, 45, false],
  [3, 30, false],
  [3, 31, true],
] as const) {
  test(`the window edge at ${h}:${String(m).padStart(2, "0")} is ${open ? "open" : "closed"}`, async ($, on) => {
    world(on, at(h, m));
    const result = await bash($, "just talos drain k8s-cp-2");
    if (open) expect(result.deny).toBeUndefined();
    else expect(String(result.deny)).toMatch(/02:45 to 03:30/);
  });
}
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
      "cat talos/secrets.yaml",
      "cd talos && yq .certs secrets.yaml",
      "cat talos/sec*",
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
test("quoted, globbed, spliced and flag-separated secret reads are refused", async ($, on) => {
  world(on);
  await denied(
    $,
    [
      'cat "cluster.toml"',
      "cat 'age.key'",
      "cat clust*",
      "cat *.toml",
      "cat cluster.tom?",
      "cat cluster.tom[l]",
      "cat cluster.{toml,}",
      "cat clu''ster.toml",
      'cat clu""ster.toml',
      "cat cluster\\.toml",
      "cat ./cluster.tom?",
      "cat /work/clust*",
      "cat talos/talos*",
      "cat *",
      "cat cluster.toml # just template",
      "cat cluster.toml template/scripts/validate.py",
      "cat -e cluster.toml",
      "head -m1 cluster.toml",
      "grep foo cluster.toml",
      "grep -e foo cluster.toml",
      "grep -f cluster.toml notes.txt",
      "grep foo <cluster.toml",
      "grep <cluster.toml foo",
      'echo "$(cat cluster.toml)"',
      "x=$(cat cluster.toml)",
      "bash -c 'cat cluster.toml'",
      'git commit -m "$(cat cluster.toml)"',
      'git commit -m "note" cluster.toml',
      "bash <<EOF\ncat cluster.toml\nEOF",
      "cat <<EOF | bash\ncat cluster.toml\nEOF",
      "bash -c 'cat \"$1\"' _ cluster.toml",
      "sh -c 'cat' < cluster.toml",
      "grep -e. cluster.toml",
      "grep -Ee. age.key",
      "rg -e. deploy.key",
      "grep --regex=. cluster.toml",
      "gh pr create --body-file - <<EOF\n$(cat age.key)\nEOF",
      "git commit -F - <<EOF\n$(cat cluster.toml)\nEOF",
      "git commit -F - <<EO'F'\nmsg\nEOF\ncat cluster.toml",
      "git commit -F - <<E\\OF\nmsg\nEOF\ncat cluster.toml",
      "git commit -Ftemplate/../cluster.toml",
      "git commit -m \"$(cat <<'EOF'\nfoo\nEOF\ncat cluster.toml\nEOF\n)\"",
      'echo "$(cat clust*)"',
      'echo "`cat clust*`"',
      "eval 'cat clust*'",
    ],
    /names a secrets file/,
  );
  await allowed($, [
    "uv run --locked --no-dev template/scripts/validate.py cluster.toml | jq -r .domain.name",
    "uv run --locked --no-dev template/scripts/check_layout.py cluster.toml",
    "just template scaffold spegel",
    "taplo check --schema file://x cluster.toml",
    'git commit -m "note cluster.toml is gitignored"',
    "git commit --message='note cluster.toml is gitignored'",
    'git commit -m "$(cat <<\'EOF\'\nnote don\'t print "cluster.toml"\ncluster.toml\nEOF\n)"',
    "git commit -q -F - <<'EOF'\nnote cluster.toml\ncat age.key; it's gitignored\nEOF",
    "git commit -F msg.txt",
    'grep -rn "cluster.toml" CLAUDE.md',
    "grep -e cluster.toml .gitignore",
    "grep cluster.toml .gitignore",
    "/usr/bin/grep -c kubeconfig CLAUDE.md",
    "rg 'talosconfig' docs/",
    "ls kubernetes/apps/*",
    "cat *.md",
    "ls cluster.sample.toml",
    "cat cluster.sample.*",
    '[[ -f x ]] && echo "[ok]"',
    'grep -A 2 "cluster.toml" CLAUDE.md',
    "rg -t md 'talosconfig' docs",
    "find . -name \\*.json",
    "find . -name '*.json'",
    "ls [z-a]*",
  ]);
});
test("op commands that print a secret are refused, the rest run", async ($, on) => {
  world(on);
  await denied(
    $,
    [
      "op read op://vault/item/field",
      "op inject --in-file bootstrap/onepassword.yaml",
      "op run -- env",
      "op document get talos --vault vault",
      "op item get 1password --format json",
      "op item --vault vault get 1password",
      "op --account work read op://vault/item/field",
      "bash -c 'op read op://vault/item/field'",
      "echo $(op read op://vault/item/field)",
    ],
    /owner's to run/,
  );
  await allowed($, [
    "op --version",
    "op whoami",
    "op vault list",
    "op item list --vault vault",
    "just bootstrap apps",
  ]);
});
test("just's flags and module path do not hide node maintenance", async ($, on) => {
  world(on, at(3, 0));
  await denied(
    $,
    [
      "just --yes talos drain k8s-worker-1",
      "just -f justfile talos drain k8s-worker-1",
      "just talos::drain k8s-worker-1",
    ],
    /02:45 to 03:30/,
  );
  await allowed($, ["just talos health"]);
});
test("nested shells, other redirects and exec forms still count as writes", async ($, on) => {
  world(on);
  await denied(
    $,
    [
      "bash -c 'echo x > kubernetes/a.yaml'",
      "sh -c 'sed -i s/a/b/ talos/all/1.yaml'",
      "echo x >| kubernetes/a.yaml",
      "echo x &> kubernetes/a.yaml",
      "echo x &>> kubernetes/a.yaml",
      "echo x 2>| kubernetes/a.yaml",
      "cp -t kubernetes/ src.yaml",
      "mv --target-directory=talos/all src.yaml",
      "find kubernetes -name x -exec sed -i s/a/b/ {} +",
      "find talos -name x -delete",
      "ls | xargs sed -i s/a/b/ kubernetes/a.yaml",
      "ls | xargs -n 1 sed -i s/a/b/ kubernetes/a.yaml",
      "bash -c 'echo x' > kubernetes/a.yaml",
      'echo "$(sed -i s/a/b/ kubernetes/a.yaml)"',
      "eval 'echo x > kubernetes/a.yaml'",
      "find kubernetes -exec grep -l foo {} \\; -exec sed -i s/a/b/ {} \\;",
      "find -L kubernetes -delete",
      "find . -name x -exec cp {} kubernetes/a.yaml \\;",
    ],
    /writes a rendered file/,
  );
  await allowed($, [
    "find kubernetes -name '*.yaml' -exec cp {} /tmp/x \\;",
    "bash -c 'cat kubernetes/a.yaml'",
    "find kubernetes -name x",
    "find kubernetes -name x -exec grep -l foo {} +",
    "ls kubernetes | xargs -n 1 echo",
    "cmd 2>&1 | tee /tmp/out",
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
test("talos/rendered machine configs count as secrets files", async ($, on) => {
  world(on);
  await denied(
    $,
    [
      "cat talos/rendered/k8s-cp-1.yaml",
      "yq .machine.token ./talos/rendered/k8s-cp-1.yaml",
      "cat /work/talos/rendered/k8s-cp-1.yaml",
      "ls talos/rendered",
      "cat talos/re*/k8s-cp-1.yaml",
      "grep -r token talos/*/*.yaml",
    ],
    /names a secrets file/,
  );
  await allowed($, ["just talos render", "cat talos/all/10.yaml"]);
});
test("an rtk prefix does not hide the real command", async ($, on) => {
  world(on);
  await allowed($, [
    'rtk grep -n "secrets.yaml\\|x" talos/mod.just',
    'rtk bypass grep -n "secrets.yaml" talos/mod.just',
    'RTK_DISABLED=1 grep -n "secrets.yaml" talos/mod.just',
  ]);
  await denied(
    $,
    ["rtk cat talos/secrets.yaml", "rtk bypass cat cluster.toml", "RTK_DISABLED=1 cat age.key"],
    /names a secrets file/,
  );
  await denied($, ["rtk op read op://vault/item/field"], /owner's to run/);
  await denied($, ["rtk sed -i s/a/b/ kubernetes/a.yaml"], /writes a rendered file/);
});
test("a quoted heredoc written to a file is data unless an interpreter reads it", async ($, on) => {
  world(on);
  await allowed($, [
    "cat > \"$TMPDIR/x\" <<'EOF'\ncat talos/secrets.yaml\nEOF",
    "tee \"$TMPDIR/t.sh\" >/dev/null <<'EOF'\ndocker run -v ./kubeconfig:/k img\nEOF",
  ]);
  await denied(
    $,
    [
      "bash <<'EOF'\ncat talos/secrets.yaml\nEOF",
      "python3 - <<'EOF'\nopen('cluster.toml')\nEOF",
      "uv run python - <<'EOF'\nopen('cluster.toml')\nEOF",
      "node <<'EOF'\nrequire('fs').readFileSync('age.key')\nEOF",
      "cat <<'EOF' | sh\ncat age.key\nEOF",
      "xargs cat <<'EOF'\ntalos/secrets.yaml\nEOF",
      'cat > "$TMPDIR/x" <<EOF\n$(cat cluster.toml)\nEOF',
      "cat > \"$TMPDIR/x\" <<'EOF'\nok\nEOF\ncat cluster.toml",
      "php <<'EOF'\n<?php readfile('talos/secrets.yaml');\nEOF",
      "lua - <<'EOF'\nio.open('age.key')\nEOF",
      "cat <<'EOF' | npx tsx -\nrequire('fs').readFileSync('cluster.toml')\nEOF",
    ],
    /names a secrets file/,
  );
  await denied(
    $,
    ["git add . && cat > \"$TMPDIR/n.md\" <<'EOF'\ncat cluster.toml\nEOF"],
    /names a secrets file/,
  );
});
test("rtk flags, rtk readers and talos/rendered look-alikes", async ($, on) => {
  world(on);
  await allowed($, [
    "rtk uv run --locked --no-dev template/scripts/validate.py cluster.toml",
    "rtk just template doctor",
    "cat talos/rendered-notes.md",
  ]);
  await denied(
    $,
    ["rtk -u cat talos/secrets.yaml", "cat talos/rendered/k8s-cp-1.yaml"],
    /names a secrets file/,
  );
  await denied($, ["rtk -u sed -i s/a/b/ kubernetes/apps/x.yaml"], /rendered/);
});
test("a flag name is not a file reference, its value may be", async ($, on) => {
  world(on);
  await allowed($, ["true --kubeconfig /dev/null", "talosctl --talosconfig=/tmp/x version"]);
  await denied(
    $,
    ["kubectl --kubeconfig ./kubeconfig get nodes", "kubectl --kubeconfig=./kubeconfig get nodes"],
    /names a secrets file/,
  );
});
