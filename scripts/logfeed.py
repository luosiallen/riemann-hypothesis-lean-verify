#!/usr/bin/env python3
"""Build-log feed for the public dashboard.

Reads the server's build logs and writes <out>/logs.json (recent build lines, slowest modules,
warning categories, recent warnings, errors, scheduler counters) and <out>/build_tail.txt
(last 2,000 build-log lines). Absolute paths are cut down to project-relative ones.
Usage: logfeed.py <out_dir>
"""
import json, os, re, sys, time
from collections import Counter

ROOT = "/home/allenluo/rhv"
PROJ = f"{ROOT}/src/lean/"
BUILD = f"{ROOT}/logs/build.log"
WARN = f"{ROOT}/logs/warnings.log"
ERRDIR = f"{ROOT}/logs/errors"
SCHED = f"{ROOT}/kv/sched_stats.txt"
EVENTS = f"{ROOT}/events.json"
RES = f"{ROOT}/repo/results"
ROUT = f"{ROOT}/kv/replay/out"
WALKS = ["riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re",
         "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive"]
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/status"

LINE = re.compile(r"^(✔|⚠|✖)\s*\[(\d+)/(\d+)\]\s+\S+\s+(\S+)(?:\s+\(([\d.]+)(ms|s)\))?")
WLINE = re.compile(r"^(?:\S*/)?(src/\S+?\.lean):(\d+):(\d+): (warning|error): (.*)$")


def rel(s):
    return s.replace(PROJ, "").replace(ROOT + "/", "")


def tail_bytes(path, n):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", "replace"), size
    except OSError:
        return "", 0


def build_info():
    recent, slow, counts = [], [], Counter()
    try:
        with open(BUILD, errors="replace") as f:
            for ln in f:
                m = LINE.match(ln)
                if not m:
                    continue
                icon, _, _, mod, t, unit = m.groups()
                counts[icon] += 1
                secs = float(t) / (1000 if unit == "ms" else 1) if t else None
                if secs is not None:
                    slow.append((secs, mod))
                    if len(slow) > 400:
                        slow.sort(reverse=True)
                        del slow[40:]
                recent.append(ln.rstrip())
                if len(recent) > 400:
                    del recent[:-60]
    except OSError:
        pass
    slow.sort(reverse=True)
    rows = []
    for ln in recent[-60:]:
        m = LINE.match(ln)
        icon, i, n, mod, t, unit = m.groups()
        rows.append({"s": {"✔": "ok", "⚠": "warn", "✖": "fail"}[icon], "i": int(i), "m": mod,
                     "t": (float(t) / (1000 if unit == "ms" else 1)) if t else None})
    return rows, [{"m": m, "t": round(s, 1)} for s, m in slow[:12]], counts


def warn_info():
    text, size = tail_bytes(WARN, 400_000)
    kinds, recent = Counter(), []
    for ln in text.splitlines():
        m = WLINE.match(rel(ln.strip()))
        if not m:
            continue
        path, line, col, sev, msg = m.groups()
        k = re.sub(r"`[^`]*`", "`…`", msg)
        k = re.sub(r"'[^']*'", "'…'", k)
        k = k.split(":")[0][:70]
        kinds[k] += 1
        recent.append(f"{path}:{line}:{col}: {sev}: {msg[:160]}")
    return [{"k": k, "n": n} for k, n in kinds.most_common(8)], recent[-25:], size


def error_info():
    out = []
    try:
        names = [n for n in os.listdir(ERRDIR) if n.endswith(".log") and not n.startswith(".")]
        names.sort(key=lambda n: os.path.getmtime(os.path.join(ERRDIR, n)))
    except OSError:
        return 0, out
    for n in names[-15:]:
        try:
            with open(os.path.join(ERRDIR, n), errors="replace") as f:
                body = rel(f.read(1500)).strip()
        except OSError:
            body = ""
        out.append({"name": n, "body": body})
    return len(names), out


def sched_info():
    try:
        parts = open(SCHED).read().split()
    except OSError:
        return None
    d = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            try:
                d[k] = float(v) if "." in v else int(v)
            except ValueError:
                pass
    d["at"] = int(parts[0]) if parts and parts[0].isdigit() else None
    return d


def _fresh(path, since):
    """Read a file only if it was written after `since` (so stale files from earlier runs are ignored)."""
    try:
        if since and os.path.getmtime(path) < since - 5:
            return None
        return open(path, errors="replace").read()
    except OSError:
        return None


def _mt(path):
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return None


def _items(items):
    """items: (name, ok, file) -> [{"n", "ok", "t"}]; t = UTC epoch the check's output was finished."""
    return [{"n": n, "ok": ok, "t": _mt(f) if ok else None} for n, ok, f in items]


def stage_info():
    """Progress of each verification stage, for the overall bar and the phase rows."""
    try:
        ph = {p["id"]: p for p in json.load(open(EVENTS))["phases"]}
    except (OSError, ValueError, KeyError):
        return None
    out = {}
    sc = sched_info() or {}
    if sc.get("total"):
        out["build"] = {"done": sc.get("done", 0), "total": sc["total"], "unit": "modules"}
    # axioms: Audit.lean (#print axioms) + 5 independent axiom walks
    a = ph.get("axioms", {})
    if a.get("state") == "running":
        since = a.get("start")
        items = [("#print axioms (Audit.lean)", "AUDIT_EXIT" in (_fresh(f"{RES}/audit.log", since) or ""), f"{RES}/audit.log")]
        items += [(f"axiom walk: {t}", "WALK_EXIT" in (_fresh(f"{ROUT}/walk_{t}.txt", since) or ""), f"{ROUT}/walk_{t}.txt")
                  for t in WALKS]
        out["axioms"] = {"done": sum(ok for _, ok, _ in items), "total": len(items), "unit": "checks", "items": _items(items)}
    st = ph.get("statement", {})
    if st.get("state") == "running":
        since = st.get("start")
        items = [("StatementAudit.lean", "STATEMENT_AUDIT_EXIT" in (_fresh(f"{RES}/statement_audit.txt", since) or ""),
                  f"{RES}/statement_audit.txt"),
                 ("Main import closure", _fresh(f"{ROUT}/main_closure.rc", since) is not None, f"{ROUT}/main_closure.rc"),
                 ("package revisions", _fresh(f"{RES}/package_revs.txt", since) is not None, f"{RES}/package_revs.txt")]
        out["statement"] = {"done": sum(ok for _, ok, _ in items), "total": len(items), "unit": "checks", "items": _items(items)}
    r = ph.get("replay", {})
    if r.get("state") == "running":
        since = r.get("start")
        mods = _fresh(f"{ROUT}/replay_modules.txt", since)
        cdir = f"{ROUT}/chunks"
        total = len(mods.split()) if mods else None
        ok = bad = cdone = ctotal = 0
        try:
            names = os.listdir(cdir) if os.path.getmtime(cdir) >= (since or 0) - 5 else []
        except OSError:
            names = []
        for n in names:
            if not n.endswith(".out"):
                ctotal += 1
                continue
            try:
                txt = open(os.path.join(cdir, n), errors="replace").read()
            except OSError:
                continue
            ok += len(re.findall(r"^OK ", txt, re.M))
            bad += len(re.findall(r"^FAIL ", txt, re.M))
            cdone += "\nRC " in "\n" + txt
        xc = _fresh(f"{RES}/leanchecker_crosscheck.txt", since) or ""
        xdone = len(re.findall(r" rc=\d+ ", xc))
        try:
            xtotal = len(open(f"{ROOT}/kv/replay/crosscheck.txt").read().split())
        except OSError:
            xtotal = 59
        el = time.time() - since if since else None
        rate = ok / el * 60 if el and el > 60 and ok else None
        out["replay"] = {"done": ok, "total": total, "failed": bad, "unit": "modules",
                         "chunks_done": cdone, "chunks_total": ctotal,
                         "crosscheck_done": xdone, "crosscheck_total": xtotal,
                         "rate_per_min": round(rate, 1) if rate else None,
                         "eta_seconds": int((total - ok) / rate * 60) if rate and total else None}
    return out


def _clip(text, n=None, w=400):
    lines = [rel(l).replace("/home/allenluo", "~")[:w] for l in text.splitlines()]
    return "\n".join(lines[-n:] if n else lines)


def phase_logs():
    """Raw output of each post-compile phase, as {phase: [{"f": file label, "t": text}]}."""
    try:
        ph = {p["id"]: p for p in json.load(open(EVENTS))["phases"]}
    except (OSError, ValueError, KeyError):
        return None
    out = {}

    def files(pid, items):
        # Outputs are overwritten on each pipeline (re)start, so anything newer than this run's compile start is current.
        since = ph.get("build", {}).get("start")
        if not since or ph[pid].get("state") == "pending":
            return
        got = []
        for label, path, n in items:
            t = _fresh(path, since)
            if t:
                got.append({"f": label, "t": _clip(t, n)})
        if got:
            out[pid] = got

    walks = [(f"walk_{t}.txt", f"{ROUT}/walk_{t}.txt", None) for t in WALKS]
    files("axioms", [("results/audit.log  (#print axioms)", f"{RES}/audit.log", None)] + walks)
    files("statement", [("results/statement_audit.txt", f"{RES}/statement_audit.txt", None),
                        ("results/package_revs.txt", f"{RES}/package_revs.txt", None)])
    r = ph.get("replay", {})
    if r.get("start") and r.get("state") != "pending":
        since, cdir, got = r["start"], f"{ROUT}/chunks", []
        try:
            outs = [os.path.join(cdir, n) for n in os.listdir(cdir) if n.endswith(".out")]
            outs = [f for f in outs if os.path.getmtime(f) >= since - 5]
            outs.sort(key=os.path.getmtime)
        except OSError:
            outs = []
        recent, fails = [], []
        for f in outs[-12:]:
            try:
                recent += [l for l in open(f, errors="replace").read().splitlines() if l.startswith(("OK ", "FAIL "))][-5:]
            except OSError:
                pass
        for f in outs:
            try:
                txt = open(f, errors="replace").read()
            except OSError:
                continue
            if "FAIL " in txt:
                fails += [l for l in txt.splitlines() if l.startswith("FAIL ")]
        if recent:
            got.append({"f": "replayexact · latest results (OK = module re-checked by the kernel, with time)", "t": _clip("\n".join(recent[-40:]))})
        got.append({"f": "replayexact · failures", "t": _clip("\n".join(fails[:50])) if fails else "(none)"})
        for label, path, n in [("results/replay_summary.txt", f"{RES}/replay_summary.txt", None),
                               ("results/leanchecker_crosscheck.txt", f"{RES}/leanchecker_crosscheck.txt", 80),
                               ("results/negative_control.txt", f"{RES}/negative_control.txt", None),
                               ("results/fresh_replay.txt  (supplementary)", f"{RES}/fresh_replay.txt", None)]:
            t = _fresh(path, since)
            if t:
                got.append({"f": label, "t": _clip(t, n)})
        out["replay"] = got
    try:
        out["pipeline"] = [{"f": "kv/chain.log  (post-compile pipeline)",
                            "t": _clip(tail_bytes(f"{ROOT}/kv/chain.log", 20000)[0], 30, 300)}]
    except Exception:
        pass
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, slow, counts = build_info()
    kinds, wrecent, wsize = warn_info()
    nerr, errs = error_info()
    feed = {
        "updated": int(time.time()),
        "recent": rows,
        "slowest": slow,
        "counts": {"ok": counts["✔"], "warn": counts["⚠"], "fail": counts["✖"]},
        "warning_kinds": kinds,
        "recent_warnings": wrecent,
        "warnings_log_mb": round(wsize / 1e6, 1),
        "error_files": nerr,
        "errors": errs,
        "scheduler": sched_info(),
        "stages": stage_info(),
        "phase_logs": phase_logs(),
        "logs_published": os.path.exists(f"{ROOT}/status/.logs_published"),
    }
    tmp = f"{OUT}/logs.json.tmp"
    json.dump(feed, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, f"{OUT}/logs.json")
    text, _ = tail_bytes(BUILD, 600_000)
    lines = [rel(l) for l in text.splitlines()[1:]][-2000:]
    tmp = f"{OUT}/build_tail.txt.tmp"
    open(tmp, "w").write("\n".join(lines) + "\n")
    os.replace(tmp, f"{OUT}/build_tail.txt")


if __name__ == "__main__":
    main()
