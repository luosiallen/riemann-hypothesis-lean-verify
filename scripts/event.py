#!/usr/bin/env python3
"""Update phase timeline: event.py <phase_id> <pending|running|done|failed> [note]"""
import json, os, sys, time
F = "/home/allenluo/rhv/events.json"
PHASES = [
    ("download", "Download 14 archive parts (parallel)"),
    ("static", "Static audit: sorry / axiom / native_decide / kernel bypass"),
    ("toolchain", "Install Lean v4.33.1 + Mathlib prebuilt cache"),
    ("build", "Kernel-check all 175,187 modules (lake build, 128 cores)"),
    ("axioms", "#print axioms on the final theorems"),
    ("statement", "Confirm statements match Mathlib definitions"),
    ("replay", "Independent environment replay (lean4checker)"),
]
d = json.load(open(F)) if os.path.exists(F) else {"phases": [{"id": i, "name": n, "state": "pending"} for i, n in PHASES], "notes": []}
pid, state = sys.argv[1], sys.argv[2]
ts = int(sys.argv[4]) if len(sys.argv) > 4 else int(time.time())
for p in d["phases"]:
    if p["id"] == pid:
        p["state"] = state
        if state == "running": p["start"] = ts
        if state in ("done", "failed"):
            p.setdefault("start", ts); p["end"] = ts
        if len(sys.argv) > 3 and sys.argv[3]:
            p["note"] = sys.argv[3]
json.dump(d, open(F, "w"), indent=1, ensure_ascii=False)
