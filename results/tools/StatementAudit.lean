import Main
open Lean Elab Command

/-! Statement audit (run 2). The marked section 4 needs `Main`; the rest only needs `Statements`. -/

#print RiemannHypothesis
#print riemannZeta
#print DirichletCharacter.LFunction
#print DirichletCharacter.IsPrimitive
#print RiemannZetaZerosOnLine
#print DirichletLNonvanishingRightOfHalf
#print DirichletLZerosOnLine
#print PrimitiveDirichletLZerosOnLine

/-- The project's zeta statement is (definitionally, by `rfl`) Mathlib's `RiemannHypothesis`. -/
example : RiemannZetaZerosOnLine = RiemannHypothesis := rfl

run_cmd do
  let env ← getEnv
  let mut ok := true
  let modOf (n : Name) : Option Name :=
    (env.getModuleIdxFor? n).map fun i => env.header.moduleNames[i.toNat]!
  let projectRoots : List Name := [`BuildAid, `CompanionTheory, `Development, `Formalism,
    `GroundTheory, `Lemmata, `PositivityTheory, `ReciprocityTheory, `Supplements, `Main, `Statements]
  -- 1. Mathlib-side notions really come from Mathlib modules
  for n in [``RiemannHypothesis, ``riemannZeta, ``DirichletCharacter, ``DirichletCharacter.LFunction,
            ``DirichletCharacter.IsPrimitive, ``Complex.re, ``NeZero] do
    match modOf n with
    | some m =>
      if m.getRoot == `Mathlib || m.getRoot == `Init then logInfo m!"ORIGIN_OK {n} ← {m}"
      else ok := false; logError m!"ORIGIN_BAD {n} ← {m}"
    | none => ok := false; logError m!"ORIGIN_BAD {n}: not from an imported module"
  -- 2. The four project-side statement definitions live in `Statements`, which imports only Mathlib
  let stmts : List Name := [`RiemannZetaZerosOnLine, `DirichletLNonvanishingRightOfHalf,
    `DirichletLZerosOnLine, `PrimitiveDirichletLZerosOnLine]
  for n in stmts do
    if modOf n == some `Statements then logInfo m!"ORIGIN_OK {n} ← Statements"
    else ok := false; logError m!"ORIGIN_BAD {n} ← {modOf n}"
  match env.getModuleIdxFor? `RiemannZetaZerosOnLine with
  | some i =>
    let imps := env.header.moduleData[i.toNat]!.imports.map (·.module)
    if imps.all (fun m => m == `Mathlib || m == `Init) && imps.contains `Mathlib then
      logInfo m!"STATEMENTS_IMPORTS_OK {imps.toList}"
    else ok := false; logError m!"STATEMENTS_IMPORTS_BAD {imps.toList}"
  | none => ok := false; logError "Statements module not found"
  -- 3. Every constant referenced by the statement definitions comes from Mathlib/core, not the project
  -- (auxiliary constants such as `RiemannZetaZerosOnLine._proof_1` generated inside `Statements`
  --  are followed transitively; everything else must come from Mathlib or core)
  for n in stmts do
    let ci ← liftCoreM <| getConstInfo n
    let mut stack : Array Name := #[n]
    let mut seen : NameSet := {}
    let mut ext : NameSet := {}
    let mut bad : Array Name := #[]
    while h : stack.size > 0 do
      let c := stack.back
      stack := stack.pop
      if seen.contains c then continue
      seen := seen.insert c
      match modOf c with
      | some `Statements =>
        let some cci := env.find? c | bad := bad.push c; continue
        for d in cci.type.getUsedConstants ++ (cci.value?.map (·.getUsedConstants)).getD #[] do
          stack := stack.push d
      | some m => if projectRoots.contains m.getRoot then bad := bad.push c else ext := ext.insert c
      | none => bad := bad.push c
    let aux := seen.toList.filter (fun c => c != n && modOf c == some `Statements)
    if ci.levelParams.isEmpty && bad.isEmpty && ci.isDefinition then
      logInfo m!"STMT_DEPS_OK {n}: {ext.size} external constants (Mathlib/core), auxiliary in Statements: {aux}"
    else ok := false; logError m!"STMT_DEPS_BAD {n}: project/unknown refs {bad.toList}"
  -- BEGIN_MAIN
  -- 4. The final theorems are theorems whose types are literally the statement constants
  for (t, s) in [(`riemannHypothesis, ``RiemannHypothesis), (`riemannZeta_eq_zero_re, `RiemannZetaZerosOnLine),
      (`LFunction_ne_zero_of_half_lt_re, `DirichletLNonvanishingRightOfHalf),
      (`LFunction_eq_zero_re, `DirichletLZerosOnLine),
      (`LFunction_eq_zero_re_of_isPrimitive, `PrimitiveDirichletLZerosOnLine)] do
    let ci ← liftCoreM <| getConstInfo t
    let isThm := match ci with | .thmInfo _ => true | _ => false
    if isThm && ci.type == mkConst s && ci.levelParams.isEmpty && modOf t == some `Main then
      logInfo m!"THM_TYPE_OK {t} : {s} (theorem in Main)"
    else ok := false; logError m!"THM_TYPE_BAD {t}: kind/type/module mismatch ({ci.type}, {modOf t})"
  -- END_MAIN
  if ok then logInfo "STATEMENT_AUDIT_OK" else logError "STATEMENT_AUDIT_FAILED"
