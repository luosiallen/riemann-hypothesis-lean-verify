#!/usr/bin/env python3
"""High-concurrency replacement for `lake build` on a very wide module graph.

Lake 4.33 spends most of its CPU building per-module transitive import closures (setup.json) under a shared
lock; with 175k modules on 288 cores only a handful of `lean` processes ran.  This driver:
  * parses `import` headers of every module under src/ into a DAG (local modules only; packages are prebuilt),
  * treats a module as done when its .olean and .ilean both exist and are newer than the source,
  * keeps up to JOBS `lean` processes running, highest critical-path first,
  * holds back new launches while MemAvailable is below MEM_FLOOR_GB,
  * runs the toolchain's `lean` with exactly the lakefile's options, so the kernel check is the same.
Log format matches Lake's (`✔ [k/N] Built M (Xs)`), and `EXIT <code>` is written only on natural completion.
"""
import heapq, os, re, signal, subprocess, sys, time

ROOT = "/home/allenluo/rhv"
PROJ = f"{ROOT}/src/lean"
SRC = f"{PROJ}/src"
OUT = f"{PROJ}/.lake/build/lib/lean"
LOG = os.environ.get("SCHED_LOG", f"{ROOT}/logs/build.log")
ERRDIR = f"{ROOT}/logs/errors"
WARNLOG = f"{ROOT}/logs/warnings.log"
STATS = f"{ROOT}/kv/sched_stats.txt"
LEAN = os.path.expanduser("~/.elan/toolchains/leanprover--lean4---v4.33.1/bin/lean")
JOBS = int(os.environ.get("JOBS", "288"))
MEM_FLOOR_GB = float(os.environ.get("MEM_FLOOR_GB", "96"))
LEAN_PATH = open(f"{ROOT}/kv/LEAN_PATH").read().strip()
BASE_ARGS = ["--tstack=400000", "-DrelaxedAutoImplicit=false", "-Dpp.unicode.fun=true",
             "-DmaxSynthPendingDepth=3", "-DmaxHeartbeats=4000000", "-DautoImplicit=false"]
FIELDS_PREFIX = ("GroundTheory.LocalFields.", "GroundTheory.GlobalFields.")
FIELDS_ARGS = ["-DsynthInstance.maxHeartbeats=400000"]

IMPORT_RE = re.compile(r"^import\s+(.*)$")


def header_imports(path):
    """Imports from the module header (stops at the first non-import, non-comment line)."""
    imps, in_block = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            # strip block comments (may span lines; nesting counted roughly)
            out, i = "", 0
            while i < len(line):
                if line.startswith("/-", i):
                    in_block += 1; i += 2; continue
                if in_block and line.startswith("-/", i):
                    in_block -= 1; i += 2; continue
                if not in_block:
                    out += line[i]
                i += 1
            line = out.split("--", 1)[0].strip()
            if not line:
                continue
            m = IMPORT_RE.match(line)
            if not m:
                if line == "prelude":
                    continue
                break
            imps.extend(m.group(1).split())
    return imps


def mod_of(rel):
    return rel[:-5].replace("/", ".")


def path_of(mod, root, ext):
    return f"{root}/{mod.replace('.', '/')}{ext}"


def mem_available_gb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576
    return 1e9


def main():
    t0 = time.time()
    os.makedirs(ERRDIR, exist_ok=True)
    log = open(LOG, "a", buffering=1)
    warnlog = open(WARNLOG, "a", buffering=1)
    log.write(f"START {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} driver=sched.py JOBS={JOBS} "
              f"MEM_FLOOR_GB={MEM_FLOOR_GB}\n")

    # 1. module list and graph
    mods = []
    for d, _, files in os.walk(SRC):
        for fn in files:
            if fn.endswith(".lean"):
                mods.append(mod_of(os.path.relpath(os.path.join(d, fn), SRC)))
    mods.sort()
    modset = set(mods)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        imps = list(ex.map(header_imports, [path_of(m, SRC, ".lean") for m in mods], chunksize=256))
    deps = {m: [i for i in ims if i in modset] for m, ims in zip(mods, imps)}
    rdeps = {m: [] for m in mods}
    for m, ds in deps.items():
        for d in ds:
            rdeps[d].append(m)
    N = len(mods)
    log.write(f"GRAPH modules={N} local_edges={sum(len(v) for v in deps.values())} "
              f"parse_s={time.time() - t0:.1f}\n")

    # 2. critical-path height (longest chain of dependents), via reverse topological order
    indeg = {m: len(deps[m]) for m in mods}
    order, q = [], [m for m in mods if indeg[m] == 0]
    tmp = dict(indeg)
    while q:
        m = q.pop()
        order.append(m)
        for r in rdeps[m]:
            tmp[r] -= 1
            if tmp[r] == 0:
                q.append(r)
    if len(order) != N:
        log.write(f"CYCLE detected: {N - len(order)} modules unreachable\n")
    height = {}
    for m in reversed(order):
        height[m] = 1 + max((height[r] for r in rdeps[m]), default=0)
    log.write(f"CRITICAL_PATH modules={max(height.values(), default=0)}\n")

    # 3. what is already built (olean + ilean newer than source)
    def built(m):
        try:
            s = os.stat(path_of(m, SRC, ".lean")).st_mtime
            return (os.stat(path_of(m, OUT, ".olean")).st_mtime >= s and
                    os.stat(path_of(m, OUT, ".ilean")).st_mtime >= s)
        except FileNotFoundError:
            return False

    done = {m for m in mods if built(m)}
    ok_count = len(done)
    log.write(f"ALREADY_BUILT {ok_count}\n")
    if os.environ.get("DRYRUN"):
        return
    remaining_deps = {m: sum(1 for d in deps[m] if d not in done) for m in mods if m not in done}
    ready = [(-height[m], m) for m, c in remaining_deps.items() if c == 0]
    heapq.heapify(ready)

    env_base = dict(os.environ, LEAN_PATH=LEAN_PATH)
    running = {}          # pid -> (mod, start, proc, outfile)
    failed, blocked = [], set()
    stop = {"flag": False}

    def on_term(sig, frm):
        stop["flag"] = True
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    last_stats = 0
    while (ready or running) and not stop["flag"]:
        # launch
        while ready and len(running) < JOBS:
            if len(running) > 8 and mem_available_gb() < MEM_FLOOR_GB:
                break
            _, m = heapq.heappop(ready)
            olean, ilean = path_of(m, OUT, ".olean"), path_of(m, OUT, ".ilean")
            os.makedirs(os.path.dirname(olean), exist_ok=True)
            # -R SRC: module name = path relative to srcDir (as Lake's setup "name"); without it Lean names
            # the module src.<Path>, which changes private/auto-generated names (run-2c incident).
            args = [LEAN, "-R", SRC] + BASE_ARGS + (FIELDS_ARGS if m.startswith(FIELDS_PREFIX) else []) + \
                   [path_of(m, SRC, ".lean"), "-o", olean, "-i", ilean]
            # threads per lean process: few when the frontier is wide, more when it is narrow
            width = len(ready) + len(running) + 1
            nthreads = max(2, min(64, (2 * 288) // width))
            env = dict(env_base, LEAN_NUM_THREADS=str(nthreads))
            outpath = f"{ERRDIR}/.{m}.out"
            outf = open(outpath, "w")
            p = subprocess.Popen(args, cwd=PROJ, env=env, stdout=outf, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL)
            running[p.pid] = (m, time.time(), p, outf, outpath)
        if not running:
            break
        # wait for any child
        try:
            pid, status = os.waitpid(-1, 0)
        except ChildProcessError:
            break
        except InterruptedError:
            continue
        if pid not in running:
            continue
        m, st, p, outf, outpath = running.pop(pid)
        p.returncode = os.waitstatus_to_exitcode(status)
        outf.close()
        dt = time.time() - st
        out = ""
        try:
            if os.path.getsize(outpath):
                with open(outpath, errors="replace") as f:
                    out = f.read()
        except OSError:
            pass
        if p.returncode == 0:
            ok_count += 1
            done.add(m)
            mark = "⚠" if out else "✔"
            log.write(f"{mark} [{ok_count}/{N}] Built {m} ({dt:.1f}s)\n")
            if out:
                warnlog.write(f"== {m}\n{out}\n")
                for ln in out.splitlines():
                    if "declaration uses 'sorry'" in ln:
                        log.write(ln[:400] + "\n")
            os.unlink(outpath)
            for r in rdeps[m]:
                if r in remaining_deps:
                    remaining_deps[r] -= 1
                    if remaining_deps[r] == 0 and r not in blocked:
                        heapq.heappush(ready, (-height[r], r))
        else:
            failed.append(m)
            os.replace(outpath, f"{ERRDIR}/{m}.log")
            log.write(f"✖ [{ok_count}/{N}] {m} failed (exit {p.returncode}, {dt:.1f}s), see logs/errors/{m}.log\n")
            for ln in out.splitlines():
                if ": error" in ln or ln.startswith("error"):
                    log.write("error: " + ln[:400] + "\n")
            # everything downstream is blocked
            stack = list(rdeps[m])
            while stack:
                r = stack.pop()
                if r not in blocked:
                    blocked.add(r)
                    stack.extend(rdeps[r])
        now = time.time()
        if now - last_stats > 15:
            last_stats = now
            with open(STATS + ".tmp", "w") as f:
                f.write(f"{int(now)} running={len(running)} ready={len(ready)} done={ok_count} "
                        f"failed={len(failed)} blocked={len(blocked)} total={N} memavail_gb={mem_available_gb():.0f}\n")
            os.replace(STATS + ".tmp", STATS)

    if stop["flag"]:
        for pid, (m, *_rest) in running.items():
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        log.write(f"INTERRUPTED at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} done={ok_count}/{N}\n")
        return
    el = time.time() - t0
    never = N - ok_count - len(failed) - len(blocked)
    log.write(f"SUMMARY built={ok_count}/{N} failed={len(failed)} blocked={len(blocked)} not_run={never}\n")
    log.write(f"Elapsed (wall clock) time (h:mm:ss or m:ss): {int(el // 3600)}:{int(el % 3600 // 60):02d}:{int(el % 60):02d}\n")
    code = 0 if ok_count == N else 1
    log.write(f"EXIT {code}\n")


if __name__ == "__main__":
    main()
