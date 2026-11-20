import Main

#print axioms riemannHypothesis
#print axioms riemannZeta_eq_zero_re
#print axioms LFunction_ne_zero_of_half_lt_re
#print axioms LFunction_eq_zero_re
#print axioms LFunction_eq_zero_re_of_isPrimitive

#check (riemannHypothesis : _root_.RiemannHypothesis)
#print RiemannHypothesis
#print RiemannZetaZerosOnLine
#print DirichletLNonvanishingRightOfHalf
#print DirichletLZerosOnLine
#print PrimitiveDirichletLZerosOnLine

open Lean in
run_cmd do
  let env ← getEnv
  for n in [`RiemannHypothesis, `riemannZeta, `DirichletCharacter.LFunction, `DirichletCharacter,
            `DirichletCharacter.IsPrimitive, `RiemannZetaZerosOnLine, `riemannHypothesis] do
    let some idx := env.getModuleIdxFor? n | throwError "{n}: not found in any imported module"
    logInfo m!"ORIGIN {n} ← {env.header.moduleNames[idx.toNat]!}"
