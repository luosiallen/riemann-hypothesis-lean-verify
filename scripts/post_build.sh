#!/bin/bash
# Wait for the build to finish, then run the axiom/statement audit.
export PATH=$HOME/.elan/bin:$PATH
ROOT=/home/allenluo/rhv
until grep -q '^EXIT ' $ROOT/logs/build.log; do sleep 30; done
code=$(grep '^EXIT ' $ROOT/logs/build.log | tail -1 | awk '{print $2}')
if [ "$code" != "0" ]; then python3 -I $ROOT/tools/event.py build failed "lake build exited with code $code"; exit 1; fi
python3 -I $ROOT/tools/event.py build done "lake build exited 0"
python3 -I $ROOT/tools/event.py axioms running
cd $ROOT/src/lean && lake env lean $ROOT/audit/Audit.lean > $ROOT/logs/audit.log 2>&1
echo "AUDIT_EXIT $?" >> $ROOT/logs/audit.log
