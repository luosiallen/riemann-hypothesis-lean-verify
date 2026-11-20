import Lean
open Lean
/-- Print the exact transitive import closure (as recorded in the .olean headers) of a module. -/
def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := args[0]!.toName }] {}
  for m in env.header.moduleNames do IO.println m
  IO.eprintln s!"{env.header.moduleNames.size} modules, {env.constants.map₁.size} imported constants"
  return 0
