import type { Register } from "claude-code";

const DIRS = ["bootstrap", "kubernetes", "talos"];
const RENDERED = new RegExp(`^(?:${DIRS.join("|")})(?:/|$)`);
// A combined short-flag group that carries `i`: sed -i, sed -Ei, sed -i.bak, perl -pi.
const INPLACE_SHORT = /^-[a-zA-Z]*i/;
const NODE_OPS =
  /\bjust\b[^|;&]*\btalos(?:\s+|::)(?:apply|drain|stop-node|reboot-node|upgrade-node|apply-node|reset-node|upgrade-k8s|upgrade|reset)\b|\btalosctl\b.*\b(?:upgrade|upgrade-k8s|reset|apply-config|reboot|shutdown)\b|\btopf\s+(?:apply|upgrade|reset)\b|\bkubectl\b.*\bdrain\b/;
const SECRET_FILES =
  /\b(?:cluster\.toml|age\.key|deploy\.key|cloudflare-tunnel\.json|flux-webhook-token\.txt|kubeconfig|talosconfig|secrets\.yaml)\b|\btalos\/rendered(?![\w.-])/;
// just talos render writes full machine configs, keys and tokens included, here.
const SECRET_DIR = "talos/rendered";
// What a glob in the repo root or talos/ could expand to.
const SECRET_PATHS = [
  SECRET_DIR,
  "cluster.toml",
  "age.key",
  "deploy.key",
  "cloudflare-tunnel.json",
  "flux-webhook-token.txt",
  "kubeconfig",
  "talos/talosconfig",
  "talos/secrets.yaml",
];

const ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*=/;
const WRITE_OP = /^(?:\d*(?:>>?|>\||>&)|&>>?)$/;
const OPERATOR = /&>>?|\d*(?:>>|>\||>&|>|<<<|<&|<>|<)/y;
const HEREDOC = /<<-?\s*((?:'[^']*'|"[^"]*"|\\.|[^\s;|&<>()])+)/y;
// git commit -m "$(cat <<'EOF' ... EOF)". A quoted delimiter expands nothing, so its body is text.
const HEREDOC_ARG = /"\$\(cat <<-?'([\w.-]+)'\n((?:[\s\S]*?\n)?)[ \t]*\1\s*\)"/y;
const SUBSTITUTION = /\$\(([^()]*)\)|`([^`]*)`/g;
const SHELLS = new Set(["bash", "sh", "zsh", "dash"]);
const EDITORS = new Set(["tee", "mv", "cp", "install", "rsync", "sd", "sed", "perl", "yq", "sops"]);
// grep and rg flags whose next word is their value, not the pattern.
const VALUE_FLAG =
  /^(?:-[a-zA-Z]*[ABCmtTgdD]|--(?:after-context|before-context|context|max-count|include|exclude|exclude-dir|type|glob))$/;

// text is the word with quotes resolved. pattern is the same with quoted glob characters replaced
// by a NUL, which no filename holds, so only bare globbing can match a secret's name.
type Word = { text: string; pattern: string; expands: boolean; op: boolean };

function inWindow(ms: number): boolean {
  const d = new Date(ms);
  const m = d.getHours() * 60 + d.getMinutes();
  return m >= 2 * 60 + 45 && m <= 3 * 60 + 30;
}

const basename = (word: string) => word.replace(/^.*\//, "");

// The command word and its arguments, past any VAR=value prefix and an `rtk` or `rtk bypass`
// wrapper, which runs the command after it.
function command(ws: Word[]): { base: string; args: Word[] } {
  let start = ws.findIndex((w) => !ASSIGNMENT.test(w.text));
  if (start >= 0 && basename(ws[start].text) === "rtk") {
    start++;
    while (ws[start]?.text === "bypass" || ws[start]?.text.startsWith("-")) start++;
  }
  return start < 0 || !ws[start]
    ? { base: "", args: [] }
    : { base: basename(ws[start].text), args: ws.slice(start + 1) };
}

// A quoted heredoc's body is data only when every command on its line just stores or sends text;
// fed to anything else, an unknown interpreter included, its lines may run.
function storesText(ws: Word[]): boolean {
  const { base, args } = command(ws);
  return ["cat", "tee", "gh"].includes(base) || (base === "git" && args[0]?.text === "commit");
}

// The command as its simple commands, each a list of shell words with quotes resolved. Separators
// in quotes do not split, comments are dropped, and a shell's -c argument counts as commands.
function parse(cmd: string): Word[][] {
  const segs: Word[][] = [];
  let seg: Word[] = [];
  let cur: Word | undefined;
  let heredocs: { delim: string; expands: boolean }[] = [];
  let lineStart = 0;
  const add = (text: string, bare: boolean, expands = false) => {
    cur ??= { text: "", pattern: "", expands: false, op: false };
    cur.text += text;
    cur.pattern += bare ? text : text.replace(/[*?[\]{},]/g, "\0");
    cur.expands ||= expands;
  };
  const endWord = () => {
    if (cur) seg.push(cur);
    cur = undefined;
  };
  const endSeg = () => {
    endWord();
    if (seg.length) segs.push(seg);
    seg = [];
  };
  const sticky = (re: RegExp, at: number) => {
    re.lastIndex = at;
    return re.exec(cmd);
  };
  let i = 0;
  while (i < cmd.length) {
    const c = cmd[i];
    const heredocArg = c === '"' ? sticky(HEREDOC_ARG, i) : null;
    const heredoc = c === "<" ? sticky(HEREDOC, i) : null;
    const operator = /[&<>]/.test(c) || (/\d/.test(c) && !cur) ? sticky(OPERATOR, i) : null;
    // A delimiter line inside the body ends the heredoc early, so what follows it runs.
    if (heredocArg && !heredocArg[2].split("\n").some((l) => l.trim() === heredocArg[1])) {
      add(heredocArg[2], false);
      i += heredocArg[0].length;
    } else if (c === "'") {
      const end = cmd.indexOf("'", i + 1);
      add(cmd.slice(i + 1, end < 0 ? cmd.length : end), false);
      i = end < 0 ? cmd.length : end + 1;
    } else if (c === '"') {
      let j = i + 1;
      while (j < cmd.length && cmd[j] !== '"') j += cmd[j] === "\\" ? 2 : 1;
      const body = cmd.slice(i + 1, j);
      add(body.replace(/\\(["\\$`])/g, "$1"), false, /\$\(|`/.test(body));
      for (const m of body.matchAll(SUBSTITUTION)) segs.push(...parse(m[1] ?? m[2]));
      i = j + 1;
    } else if (c === "\\") {
      if (cmd[i + 1] !== "\n") add(cmd[i + 1] ?? "", false);
      i += 2;
    } else if (c === "\n") {
      endSeg();
      i++;
      const runs = segs.slice(lineStart).some((ws) => !storesText(ws));
      for (const { delim, expands } of heredocs) {
        const lines = cmd.slice(i).split("\n");
        const end = lines.findIndex((l) => l.trim() === delim);
        const body = (end < 0 ? lines : lines.slice(0, end)).join("\n");
        i = end < 0 ? cmd.length : i + body.length + (end > 0 ? 1 : 0) + lines[end].length + 1;
        if (expands || runs) segs.push(...parse(body));
      }
      heredocs = [];
      lineStart = segs.length;
    } else if (/\s/.test(c)) {
      endWord();
      i++;
    } else if (c === "#" && !cur) {
      const end = cmd.indexOf("\n", i);
      i = end < 0 ? cmd.length : end;
    } else if (heredoc) {
      endWord();
      heredocs.push({
        delim: heredoc[1].replace(/['"\\]/g, ""),
        expands: !/['"\\]/.test(heredoc[1]),
      });
      i += heredoc[0].length;
    } else if (operator) {
      endWord();
      seg.push({ text: operator[0], pattern: "", expands: false, op: true });
      i += operator[0].length;
    } else if (";|&()`".includes(c)) {
      endSeg();
      i++;
    } else {
      add(c, true);
      i++;
    }
  }
  endSeg();
  return segs.flatMap((ws) => {
    const { base, args } = command(ws);
    if (base === "eval") return parse(args.map((w) => w.text).join(" "));
    const flag = SHELLS.has(base) ? args.findIndex((w) => /^-[a-zA-Z]*c$/.test(w.text)) : -1;
    if (flag < 0 || !args[flag + 1]) return [ws];
    // The outer words still count: a redirect on the shell, or a file passed in as $1.
    return [ws.filter((w) => w !== args[flag + 1]), ...parse(args[flag + 1].text)];
  });
}

// Every word a segment writes to: redirect targets, tee's files, the destination of
// cp (and both ends of mv, which removes its source), and the files of an in-place
// editor, directly or through find -exec or xargs. Reading a rendered file and sending
// the result elsewhere writes none of these.
// shortcut: xargs paths on stdin and a shell run by find -exec or xargs are invisible here, only
// named paths count; parse those if a real bypass ever uses them.
function writtenWords(ws: Word[]): string[] {
  const out: string[] = [];
  ws.forEach((w, i) => {
    if (w.op && WRITE_OP.test(w.text) && ws[i + 1]) out.push(ws[i + 1].text);
  });
  const { base, args } = command(ws);
  const operands = args
    .filter((w, i) => !w.op && !args[i - 1]?.op && !w.text.startsWith("-"))
    .map((w) => w.text);
  const has = (re: RegExp) => args.some((w) => re.test(w.text));
  const targetDir = () => {
    const short = args.findIndex((w) => /^-[a-zA-Z]*t$/.test(w.text));
    const long = args.find((w) => w.text.startsWith("--target-directory="));
    return [
      ...(short >= 0 && args[short + 1] ? [args[short + 1].text] : []),
      ...(long ? [long.text.slice("--target-directory=".length)] : []),
    ];
  };
  switch (base) {
    case "tee":
      out.push(...operands);
      break;
    case "mv":
      out.push(...operands, ...targetDir());
      break;
    case "cp":
    case "install":
      if (operands.length) out.push(operands[operands.length - 1]);
      out.push(...targetDir());
      break;
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
    case "find": {
      const written = args.flatMap((w, i) => {
        if (!/^-(?:exec|execdir|ok|okdir)$/.test(w.text)) return [];
        const tail = args.slice(i + 1);
        const end = tail.findIndex((t) => t.text === "+" || t.text === ";");
        return writtenWords(end < 0 ? tail : tail.slice(0, end));
      });
      out.push(...written.filter((w) => !w.includes("{}")));
      if (has(/^-delete$/) || written.some((w) => w.includes("{}"))) {
        const paths = args.slice(args.findIndex((w) => !/^-[HLP]$/.test(w.text)));
        const flag = paths.findIndex((w) => w.text.startsWith("-"));
        out.push(...(flag < 0 ? paths : paths.slice(0, flag)).map((w) => w.text));
      }
      break;
    }
    case "xargs": {
      const editor = args.findIndex((w) => EDITORS.has(basename(w.text)));
      if (editor >= 0) out.push(...writtenWords(args.slice(editor)));
      break;
    }
  }
  return out;
}

// A word relative to the repo: absolute, $PWD and ./ forms count.
function relative(word: string, cwd: string): string {
  let p = word;
  for (const prefix of [`${cwd}/`, "$PWD/", "${PWD}/", "./"]) {
    if (p.startsWith(prefix)) {
      p = p.slice(prefix.length);
      break;
    }
  }
  return p.replace(/^.*\/home-cluster\//, "");
}

function writesRendered(parts: Word[][], cwd: string): boolean {
  return parts.some((ws) => writtenWords(ws).some((w) => RENDERED.test(relative(w, cwd))));
}

function braces(text: string): string[] {
  const m = /\{([^{}]*,[^{}]*)\}/.exec(text);
  if (!m) return [text];
  const [head, tail] = [text.slice(0, m.index), text.slice(m.index + m[0].length)];
  return m[1].split(",").flatMap((alt) => braces(head + alt + tail));
}

function globNamesSecret(text: string, cwd: string): boolean {
  if (!/[*?[]/.test(text)) return false;
  const glob = (g: string) =>
    new RegExp(
      `^${g.replace(/\[!?[^\]]+\]|[*?]|[.+^${}()|\\\][]/g, (m) => {
        if (m === "*") return "[^/]*";
        if (m === "?") return "[^/]";
        return m.length > 1 ? m.replace(/^\[!/, "[^") : `\\${m}`;
      })}$`,
    );
  const parts = relative(text, cwd).split("/");
  try {
    const re = glob(parts.join("/"));
    // A directory part that matches talos/rendered expands to the files in it.
    return (
      SECRET_PATHS.some((p) => re.test(p)) ||
      parts.slice(1).some((_, n) => glob(parts.slice(0, n + 1).join("/")).test(SECRET_DIR))
    );
  } catch {
    // An invalid class such as [z-a] matches nothing in the shell either.
    return false;
  }
}

// A long flag's name such as --kubeconfig is not a file; only its value can name one.
const flagValue = (s: string) => s.replace(/^--[\w-]+(?:=|$)/, "");

function namesSecret(w: Word, cwd: string): boolean {
  if (SECRET_FILES.test(flagValue(w.text))) return true;
  return braces(flagValue(w.pattern)).some((t) => SECRET_FILES.test(t) || globNamesSecret(t, cwd));
}

// The command forms allowed to open a secrets file, after an optional `uv run [flags]`.
function isReader(ws: Word[]): boolean {
  let t = ws.map((w) => w.text).filter((w) => !ASSIGNMENT.test(w));
  if (basename(t[0] ?? "") === "rtk") {
    t = t.slice(1);
    while (t[0] === "bypass" || t[0]?.startsWith("-")) t = t.slice(1);
  }
  if (t[0] === "uv" && t[1] === "run") {
    t = t.slice(2);
    while (t[0]?.startsWith("-")) t = t.slice(1);
  }
  return (
    /^(?:\.\/)?template\/scripts\/(?:validate|check_layout)\.py$/.test(t[0] ?? "") ||
    (t[0] === "just" && t[1] === "template") ||
    (t[0] === "taplo" && t[1] === "check")
  );
}

// The words that are text and not a file: a commit message, a grep pattern. Per command, so
// `cat -e cluster.toml` and `head -m1 cluster.toml` get no exemption, and a message that runs a
// command substitution gets none either.
function textWords(ws: Word[]): Set<Word> {
  const { base, args } = command(ws);
  const text = new Set<Word>();
  // A flag's value: the next word, or attached to the flag itself.
  const values = (next: RegExp, attached: RegExp) =>
    args.forEach((w, i) => {
      if (next.test(w.text)) {
        if (args[i + 1]) text.add(args[i + 1]);
      } else if (attached.test(w.text)) text.add(w);
    });
  if (base === "git" && args[0]?.text === "commit") {
    values(/^(?:-[aqvsn]*m|--message)$/, /^(?:-[aqvsn]*m.|--message=)/);
  } else if (["grep", "egrep", "fgrep", "rg"].includes(base)) {
    // GNU long flags take any unique prefix, so --regex= is --regexp=.
    values(/^(?:-[a-zA-Z]*e|--reg[a-z]*)$/, /^(?:-[a-zA-Z]*e.|--reg[a-z]*=)/);
    const patternFile = args.some((w) => /^-[a-zA-Z]*f|^--fil/.test(w.text));
    if (!text.size && !patternFile) {
      const pattern = args.find(
        (w, i) =>
          !w.op &&
          !args[i - 1]?.op &&
          !w.text.startsWith("-") &&
          !VALUE_FLAG.test(args[i - 1]?.text ?? ""),
      );
      if (pattern) text.add(pattern);
    }
  }
  return new Set([...text].filter((w) => !w.expands));
}

function readsSecret(parts: Word[][], cwd: string): boolean {
  return parts.some((ws) => {
    if (isReader(ws)) return false;
    const text = textWords(ws);
    return ws.some((w) => !text.has(w) && namesSecret(w, cwd));
  });
}

// The op verbs that print or inject a secret's value, wherever global flags sit. A just recipe
// that calls op is not seen here, because the command word is just.
function printsOpSecret(ws: Word[]): boolean {
  const { base, args } = command(ws);
  if (base !== "op") return false;
  const t = args.map((w) => w.text);
  return t.some(
    (w, i) =>
      /^(?:read|inject|run)$/.test(w) ||
      (/^(?:item|document)$/.test(w) && t.slice(i + 1).includes("get")),
  );
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
    const cwd = await $.session.cwd();
    const parts = parse(cmd);
    if (readsSecret(parts, cwd)) {
      return {
        deny: "that command names a secrets file; read one only with template/scripts/validate.py piped into a narrow jq path, check_layout.py, just template recipes or taplo check. A git commit message or a grep pattern may mention the name",
      };
    }
    if (parts.some(printsOpSecret)) {
      return {
        deny: "that op command prints a secret's value; reading 1Password is the owner's to run",
      };
    }
    if (writesRendered(parts, cwd)) {
      return {
        deny: "that writes a rendered file; edit the .j2 source under template/config/ and run just configure",
      };
    }
    return next(e);
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: "cluster-guard could not check the command" },
  );
};
