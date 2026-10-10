import type { Register } from "claude-code";

const DIRS = ["bootstrap", "kubernetes", "talos"];
const DIR = `(?:${DIRS.join("|")})/`;
const RENDERED = new RegExp(`^(?:${DIR}|\\.sops\\.yaml$)`);
// A rendered path as a shell operand: after whitespace, a quote, `=` or `>`, never after `template/config/`.
const RENDERED_OPERAND = new RegExp(`(?:^|[\\s"'=>])(?:\\S*/home-cluster/|\\./)?${DIR}`);
const WRITERS =
  /(?:^|[\s;])(?:tee|cp|mv|sd|yq\s+-i|sed\s+-i|sops\s+(?:-e\s+)?(?:-i|--in-place))\b|>/;
const SOPS_PATHSPEC = DIRS.map((d) => `:(top,glob)${d}/**/*.sops.*`);
const NODE_OPS =
  /\bjust\s+talos\s+(?:apply|drain|stop-node|reboot-node|upgrade-node|apply-node|reset-node|upgrade-k8s)\b|\btalosctl\b.*\b(?:upgrade|upgrade-k8s|reset|apply-config|reboot|shutdown)\b|\btopf\s+(?:apply|upgrade|reset)\b|\bkubectl\b.*\bdrain\b/;
const SECRET_FILES =
  /\b(?:cluster\.toml|age\.key|deploy\.key|cloudflare-tunnel\.json|flux-webhook-token\.txt|kubeconfig|talosconfig)\b/;
const SECRET_READERS =
  /template\/scripts\/(?:validate|check_layout)\.py|\bjust\s+template\b|\btaplo\s+check\b/;
const TRIGGER =
  /\bjust\s+(?:template\s+)?configure\b|\bgit\s+(?:commit|add|restore|stash|checkout)\b/;
const COMMIT = /\bgit\s+commit\b/;
const COMMIT_ALL = /\bgit\s+commit\b.*\s(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?:\s|$)/;
const CHURNED = /^(?:M.|.M) /;
const STAGED = /^M/;

function inWindow(ms: number): boolean {
  const d = new Date(ms);
  const m = d.getHours() * 60 + d.getMinutes();
  return m >= 2 * 60 + 45 && m <= 3 * 60 + 30;
}

// Quoted text is a message or a pattern, not a file the command opens.
function segments(cmd: string): string[] {
  return cmd.replace(/"(?:\\.|[^"\\])*"|'[^']*'/g, '""').split(/\|\||&&|[;|\n]/);
}

function count(porcelain: string, re: RegExp): number {
  return porcelain.split("\n").filter((l) => re.test(l)).length;
}

export const register: Register = (on) => {
  on("tool.call", { tool: ["Edit", "Write"] }, async ($, e, next) => {
    const cwd = await $.session.cwd();
    const rel = e.file_path.startsWith(`${cwd}/`)
      ? e.file_path.slice(cwd.length + 1)
      : e.file_path.replace(/^.*\/home-cluster\//, "");
    if (RENDERED.test(rel)) {
      return {
        deny: `${rel} is rendered by just configure; edit the .j2 source under template/config/ instead`,
      };
    }
    return next(e);
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: "cluster-guard could not check the path" },
  );

  on("tool.call", { tool: "Bash" }, async ($, e, next) => {
    const cmd = e.command;
    if (NODE_OPS.test(cmd) && inWindow(await $.clock.now())) {
      return {
        deny: "node maintenance is blocked 02:45 to 03:30 local: the UniFi gear auto-updates at 03:00 and a switch reboot mid-drain loses etcd quorum",
      };
    }
    const parts = segments(cmd);
    if (parts.some((s) => SECRET_FILES.test(s) && !SECRET_READERS.test(s))) {
      return {
        deny: "that command names a secrets file; only template/scripts/validate.py, check_layout.py, just template recipes and taplo check may read one (quote the name if it is only text)",
      };
    }
    if (parts.some((s) => WRITERS.test(s) && RENDERED_OPERAND.test(s))) {
      return {
        deny: "that writes a rendered file; edit the .j2 source under template/config/ and run just configure",
      };
    }
    if (!TRIGGER.test(cmd)) return next(e);

    const cwd = await $.session.cwd();
    const status = async () =>
      (
        await $.process.run(
          ["git", "status", "--porcelain", "--untracked-files=no", "--", ...SOPS_PATHSPEC],
          { cwd },
        )
      ).stdout;
    // Counted before the commit runs, because afterwards the committed files are clean.
    const committing = COMMIT.test(cmd)
      ? count(await status(), COMMIT_ALL.test(cmd) ? CHURNED : STAGED)
      : 0;
    const result = await next(e);
    const n = count(await status(), CHURNED);
    $.ui.status(
      n > 0
        ? `${n} *.sops.* files re-encrypted; restore with git checkout unless the secret inputs changed`
        : undefined,
    );
    if (committing > 0) $.ui.toast(`committing ${committing} re-encrypted sops files`);
    return result;
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: "cluster-guard could not check the command" },
  );
};
