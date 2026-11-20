import Lean.CoreM
import Lean.Replay
open Lean

/-!
Exact-module variant of the toolchain's `leanchecker` (src/lean/LeanChecker.lean, Lean v4.33.1).
`replayFromImports` below is copied verbatim from that file. The only difference is the driver:
the shipped CLI treats each argument as a name *prefix* (so `leanchecker Mathlib` replays every
Mathlib module) and stops at the first failure; this driver replays exactly the listed modules,
sequentially, and reports every failure.

Usage: replayexact <file-with-module-names>
-/

unsafe def replayFromImports (module : Name) : IO Unit := do
  let mFile ← findOLean module
  unless (← mFile.pathExists) do
    throw <| IO.userError s!"object file '{mFile}' of module {module} does not exist"
  -- Load all module data parts (exported, server, private)
  let mut fnames := #[mFile]
  let sFile := OLeanLevel.server.adjustFileName mFile
  if (← sFile.pathExists) then
    fnames := fnames.push sFile
    let pFile := OLeanLevel.private.adjustFileName mFile
    if (← pFile.pathExists) then
      fnames := fnames.push pFile
  let parts ← readModuleDataParts fnames
  if h : parts.size = 0 then throw <| IO.userError "failed to read module data" else
  let (mod, _) := parts[0]
  let (_, s) ← importModulesCore mod.imports |>.run
  let env ← finalizeImport s mod.imports {} 0 false false (isModule := true)
  let mut newConstants := {}
  -- Collect constants from last ("most private") part, which subsumes all prior ones
  for name in parts[parts.size-1].1.constNames, ci in parts[parts.size-1].1.constants do
    newConstants := newConstants.insert name ci
  let env' ← env.replay newConstants
  env'.freeRegions

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  let mods := (← IO.FS.lines args[0]!).filter (· ≠ "")
  let mut fails := 0
  for m in mods do
    let t0 ← IO.monoMsNow
    try
      replayFromImports m.toName
      IO.println s!"OK {m} {(← IO.monoMsNow) - t0}ms"
    catch e =>
      fails := fails + 1
      IO.println s!"FAIL {m}: {e}"
    (← IO.getStdout).flush
  IO.println s!"REPLAYEXACT_DONE {mods.size} modules, {fails} failures"
  return if fails == 0 then 0 else 1
