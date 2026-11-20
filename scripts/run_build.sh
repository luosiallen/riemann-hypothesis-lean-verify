#!/bin/bash
export PATH=$HOME/.elan/bin:$PATH
cd /home/allenluo/rhv/src/lean
/usr/bin/time -v lake build > /home/allenluo/rhv/logs/build.log 2>&1
echo "EXIT $?" >> /home/allenluo/rhv/logs/build.log
