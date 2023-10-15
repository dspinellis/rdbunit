#!/bin/sh
#
# Test Rdbunit on SQLite
#

# Fail on command errors and unset variables
set -eu

# Run the tests
cd examples
for i in *.rdbu ; do
  ../src/rdbunit/__main__.py --database=sqlite $i |
    sqlite3
done
