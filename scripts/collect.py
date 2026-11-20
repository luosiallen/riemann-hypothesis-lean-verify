#!/usr/bin/env python3
"""Collect verification progress into status.json for the live dashboard.

Reads: build log, .olean outputs, events.json (phase timeline), /proc stats.
Writes: <out>/status.json (current snapshot + downsampled history).
"""
import json, os, re, sys, time, subprocess

ROOT = "/home/allenluo/rhv"
PROJ = f"{ROOT}/src/lean"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/status"
BUILD_LOG = f"{ROOT}/logs/build.log"
EVENTS = f"{ROOT}/events.json"
HIST = f"{ROOT}/history.json"
TOTAL_MODULES = int(open(f"{ROOT}/total_modules.txt").read().strip())

LIB_TOTALS = {"Development": 141928, "Formalism": 18254, "GroundTheory": 8507, "ReciprocityTheory": 3845,
              "CompanionTheory": 2027, "PositivityTheory": 449, "Lemmata": 167, "Other": 10}

def count_oleans():
    d = f"{PROJ}/.lake/build/lib/lean"
    libs = {k: 0 for k in LIB_TOTALS}
    if not os.path.isdir(d):
        return 0, libs
    r = subprocess.run(["find", d, "-name", "*.olean", "-type", "f"], capture_output=True, text=True)
    n = 0
    for line in r.stdout.splitlines():
        n += 1
        top = line[len(d) + 1:].split("/", 1)[0]
        libs[top if top in libs else "Other"] += 1
    return n, libs

def cpu_sample():
    with open("/proc/stat") as f:
        v = list(map(int, f.readline().split()[1:]))
    idle = v[3] + v[4]
    return sum(v), idle

def cpu_util():
    t1, i1 = cpu_sample(); time.sleep(1.0); t2, i2 = cpu_sample()
    return round(100 * (1 - (i2 - i1) / max(1, t2 - t1)), 1)

def mem():
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":"); m[k] = int(v.split()[0])
    tot = m["MemTotal"] / 1048576; avail = m["MemAvailable"] / 1048576
    return round(tot, 1), round(tot - avail, 1)

def lean_procs():
    r = subprocess.run(["pgrep", "-c", "-x", "lean"], capture_output=True, text=True)
    return int(r.stdout.strip() or 0)

def parse_log():
    errors, warnings_sorry, last = [], 0, []
    if os.path.exists(BUILD_LOG):
        with open(BUILD_LOG, errors="replace") as f:
            lines = f.readlines()
        for ln in lines:
            if ln.startswith("✖") or ln.startswith("error:"):
                errors.append(ln.strip()[:300])
            if "declaration uses 'sorry'" in ln:
                warnings_sorry += 1
        last = [l.rstrip()[:200] for l in lines if l.startswith(("✔", "⚠", "✖", "info", "error"))][-8:]
    return errors, warnings_sorry, last

def main():
    os.makedirs(OUT, exist_ok=True)
    now = time.time()
    built, libs = count_oleans()
    events = json.load(open(EVENTS)) if os.path.exists(EVENTS) else {"phases": []}
    hist = json.load(open(HIST)) if os.path.exists(HIST) else []
    cpu = cpu_util(); mt, mu = mem()
    hist.append([int(now), built, cpu, mu])
    json.dump(hist, open(HIST, "w"))

    # Rate from a ~15 min window (fallback: whole history)
    rate = 0.0
    win = [h for h in hist if now - h[0] <= 900]
    if len(win) >= 2 and win[-1][0] > win[0][0]:
        rate = (win[-1][1] - win[0][1]) / (win[-1][0] - win[0][0])
    remaining = max(0, TOTAL_MODULES - built)
    eta = int(remaining / rate) if rate > 0 else None

    # Downsample history to <= 400 points for the chart
    step = max(1, len(hist) // 400)
    hs = hist[::step]
    if hs[-1] is not hist[-1]:
        hs.append(hist[-1])

    errors, sorry_warn, last = parse_log()
    status = {
        "updated": int(now),
        "total_modules": TOTAL_MODULES,
        "built_modules": built,
        "remaining_modules": remaining,
        "percent": round(100 * built / TOTAL_MODULES, 2),
        "rate_per_min": round(rate * 60, 1),
        "eta_seconds": eta,
        "cpu_percent": cpu,
        "cores": os.cpu_count(),
        "lean_processes": lean_procs(),
        "mem_total_gb": mt, "mem_used_gb": mu,
        "errors": errors[-20:], "error_count": len(errors),
        "sorry_warnings": sorry_warn,
        "recent_log": last,
        "history": hs,
        "libraries": [{"name": k, "built": libs[k], "total": t} for k, t in LIB_TOTALS.items()],
        "machine": "288 cores · 1 TB RAM",
        "run": 2,
        **events,
    }
    tmp = f"{OUT}/status.json.tmp"
    json.dump(status, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, f"{OUT}/status.json")

if __name__ == "__main__":
    main()
