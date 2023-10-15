#!/bin/sh
#
# Verify that the script and the database work as expected
#

for i in simple datatypes ; do
  if ! src/rdbunit/__main__.py --database=sqlite -e "examples/$i.rdbu" >script.sql ; then
    echo "Script failed" 1>&2
    exit 1
  fi
  if ! sqlite3 <script.sql >script.out 2>&1 ; then
    echo "Sqlite execution failed" 1>&2
    echo "Input" 1>&2
    cat -n script.sql 1>&2
    echo "Output" 1>&2
    cat -n script.out 1>&2
    exit 1
  fi
  if egrep -v -e '^ok [0-9]' -e '^[0-9]+\.\.[0-9]+.?$' script.out ; then
    echo "Test failed or it produced extraneous output" 1>&2
    exit 1
  fi
done

rm script.sql script.out
