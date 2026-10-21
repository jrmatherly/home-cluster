import type { Register } from "claude-code";

const DIRS = ["bootstrap", "kubernetes", "talos"];
const DIR = `(?:${DIRS.join("|")})/`;
const RENDERED = new RegExp(`^(?:${DIR}|\\.sops\\.yaml$)`);
const REDIRECT = /^\d*>>?$/;
// A combined short-flag group that carries `i`: sed -i, sed -Ei, sed -i.bak, perl -pi.
const INPLACE_SHORT = /^-[a-zA-Z]*i/;
const SOPS_PATHSPEC = DIRS.map((d) => `:(top,glob)${d}/**/*.sops.*`);
const NODE_OPS =
  /\bjust\s+talos\s+(?:apply|drain|stop-node|reboot-node|upgrade-node|apply-node|reset-node|upgrade-k8s|upgrade|reset)\b|\btalosctl\b.*\b(?:upgrade|upgrade-k8s|reset|apply-config|reboot|shutdown)\b|\btopf\s+(?:apply|upgrade|reset)\b|\bkubectl\b.*\bdrain\b/;
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

// The same split, with quoted text kept, for the write check: a quoted destination is
// still a destination. Separators inside quotes are masked so they do not split.
function rawSegments(cmd: string): string[] {
  const masked = cmd.replace(/"(?:\\.|[^"\\])*"|'[^']*'/g, (q) =>
    q.replace(/[;|&\n]/g, (c) => `\u0001${c.charCodeAt(0)}\u0001`),
  );
  return masked
    .split(/\|\||&&|[;|\n]/)
    .map((s) => s.replace(/\u0001(\d+)\u0001/g, (_, n: string) => String.fromCharCode(Number(n))));
}

// Shell words of one segment with quotes removed, stopping at a comment. A redirect
// glued to its target (`>file`) is split so the target is its own word.
function words(segment: string): string[] {
  const out: string[] = [];
  const re = /"((?:\\.|[^"\\])*)"|'([^']*)'|(\S+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(segment.replace(/(\d*>>?)(?=[^\s>&|])/g, "$1 ")))) {
    const w = m[1] ?? m[2] ?? m[3];
    if (m[3] !== undefined && w.startsWith("#")) break;
    out.push(w);
  }
  return out;
}

// Every word a segment writes to: redirect targets, tee's files, the destination of
// cp (and both ends of mv, which removes its source), and the files of an in-place
// editor. Reading a rendered file and sending the result elsewhere writes none of these.
function writtenWords(ws: string[]): string[] {
  const out: string[] = [];
  ws.forEach((w, i) => {
    if (REDIRECT.test(w) && ws[i + 1]) out.push(ws[i + 1]);
  });
  const start = ws.findIndex((w) => !/^[A-Za-z_][A-Za-z0-9_]*=/.test(w));
  if (start < 0) return out;
  const base = ws[start].replace(/^.*\//, "");
  const args = ws.slice(start + 1);
  const operands = args.filter(
    (w, i) => !w.startsWith("-") && !REDIRECT.test(w) && !REDIRECT.test(args[i - 1] ?? ""),
  );
  const has = (re: RegExp) => args.some((w) => re.test(w));
  switch (base) {
    case "tee":
    case "mv":
      out.push(...operands);
      break;
    case "cp":
    case "install":
    case "rsync":
      if (operands.length) out.push(operands[operands.length - 1]);
      break;
    case "sd":
      out.push(...operands.slice(2));
      break;
    case "sed":
    case "perl":
      if (has(INPLACE_SHORT) || has(/^--in-place/)) out.push(...operands);
      break;
    case "yq":
      if (has(/^(?:-i|--inplace)$/)) out.push(...operands);
      break;
    case "sops":
      if (has(/^(?:-i|--in-place)$/)) out.push(...operands);
      break;
  }
  return out;
}

// A word names a rendered file when, relative to the repo, it is under one of the
// rendered directories or is the root .sops.yaml. Absolute, $PWD and ./ forms count.
function isRendered(word: string, cwd: string): boolean {
  let p = word;
  for (const prefix of [`${cwd}/`, "$PWD/", "${PWD}/", "./"]) {
    if (p.startsWith(prefix)) {
      p = p.slice(prefix.length);
      break;
    }
  }
  return RENDERED.test(p.replace(/^.*\/home-cluster\//, ""));
}

function writesRendered(cmd: string, cwd: string): boolean {
  return rawSegments(cmd).some((s) => writtenWords(words(s)).some((w) => isRendered(w, cwd)));
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
    const cwd = await $.session.cwd();
    if (writesRendered(cmd, cwd)) {
      return {
        deny: "that writes a rendered file; edit the .j2 source under template/config/ and run just configure",
      };
    }
    if (!TRIGGER.test(cmd)) return next(e);

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
