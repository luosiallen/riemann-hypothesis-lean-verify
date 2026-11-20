import Lean
open Lean

/-!
Independent axiom collector. Unlike `#print axioms` in Lean ≥ 4.3x, which trusts per-module
pre-computed axiom tables stored in the .olean files (and silently skips missing constants),
this walks the bodies of every reachable constant in the fully imported environment and
fails loudly if a referenced constant is missing.

Usage: lean --run AxiomWalk.lean <RootModule> <thm1> <thm2> ...
-/
def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  let root := args[0]!.toName
  let env ← importModules #[{ module := root }] {} (level := .private)
  let modNames := env.header.moduleNames   -- read once: `env.header` costs ~12 ms per access on this 180k-module environment
  let allowed : List Name := [``propext, ``Classical.choice, ``Quot.sound]
  let mut bad := 0
  for t in args.drop 1 do
    let tn := t.toName
    let mut seen : Std.HashSet Name := {}
    let mut stack : Array Name := #[tn]
    let mut axs : Array Name := #[]
    let mut missing : Array Name := #[]
    let mut perPkg : Std.HashMap Name Nat := {}
    while h : stack.size > 0 do
      let c := stack.back
      stack := stack.pop
      if seen.contains c then continue
      seen := seen.insert c
      let pkg := match env.getModuleIdxFor? c with
        | some i => (modNames[i.toNat]!).getRoot
        | none => `«<current>»
      perPkg := perPkg.insert pkg (perPkg.getD pkg 0 + 1)
      let push (st : Array Name) (e : Expr) : Array Name :=
        e.getUsedConstants.foldl (init := st) fun st n => if seen.contains n then st else st.push n
      match env.constants.find? c with
      | none => missing := missing.push c
      | some (.axiomInfo v)  => axs := axs.push c; stack := push stack v.type
      | some (.defnInfo v)   => stack := push (push stack v.type) v.value
      | some (.thmInfo v)    => stack := push (push stack v.type) v.value
      | some (.opaqueInfo v) => stack := push (push stack v.type) v.value
      | some (.quotInfo v)   => stack := push stack v.type
      | some (.ctorInfo v)   => stack := push (stack.push v.induct) v.type
      | some (.recInfo v)    =>
          stack := v.rules.foldl (init := push stack v.type) fun st r => push st r.rhs
          stack := v.all.foldl (init := stack) fun st n => st.push n
      | some (.inductInfo v) =>
          stack := (v.ctors ++ v.all).foldl (init := push stack v.type) fun st n => st.push n
    axs := axs.qsort Name.lt
    let nonstd := axs.filter (fun a => !allowed.contains a)
    let pk := perPkg.toArray.qsort (fun a b => a.2 > b.2) |>.toList.map fun (p, n) => s!"{p}:{n}"
    IO.println s!"WALK {tn}: reachable={seen.size} axioms={axs.toList} missing={missing.size} byRoot={pk}"
    if !missing.isEmpty then
      IO.println s!"MISSING {tn}: {(missing.extract 0 20).toList}"
    unless (env.constants.find? tn).isSome do
      IO.println s!"NOTFOUND {tn}"; bad := bad + 1
    if !nonstd.isEmpty || !missing.isEmpty then bad := bad + 1
  IO.println s!"AXIOMWALK_BAD {bad}"
  return if bad == 0 then 0 else 1
