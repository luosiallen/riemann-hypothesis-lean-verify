#!/bin/bash
# After the audit finishes, mark phases and commit build/audit results to the main branch.
export PATH=$HOME/.local/bin:$HOME/.elan/bin:$PATH
ROOT=/home/allenluo/rhv
until grep -q '^AUDIT_EXIT' $ROOT/logs/audit.log 2>/dev/null || grep -q '^EXIT [^0]' $ROOT/logs/build.log 2>/dev/null; do sleep 30; done
mkdir -p $ROOT/repo/results
grep -E '^(✖|error)|^EXIT|Elapsed|Maximum resident' $ROOT/logs/build.log > $ROOT/repo/results/build_summary.txt
cp $ROOT/logs/audit.log $ROOT/repo/results/ 2>/dev/null
AX=$(grep -A3 "depends on axioms" $ROOT/logs/audit.log 2>/dev/null | tr -d '\n' | grep -oE '\[[^]]*\]' | tr ',' '\n' | tr -d '[] ' | sort -u | tr '\n' ' ')
BAD=$(echo "$AX" | tr ' ' '\n' | grep -vE '^(propext|Classical.choice|Quot.sound)?$')
if grep -q 'AUDIT_EXIT 0' $ROOT/logs/audit.log 2>/dev/null && [ -z "$BAD" ] && grep -q "depends on axioms" $ROOT/logs/audit.log; then
  python3 -I $ROOT/tools/event.py axioms done "Axioms used: $AX"
else
  python3 -I $ROOT/tools/event.py axioms failed "Audit problem. Axioms: ${AX:-none reported}; non-standard: ${BAD:-none}"
fi
cd $ROOT/repo && git add -A && git commit -q -m "Add build summary and axiom audit output

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q origin main
