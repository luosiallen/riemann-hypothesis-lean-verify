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
