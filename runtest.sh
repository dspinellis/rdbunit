#!/bin/sh

PYTHON="$1"
shift

for i ; do
  if ! $PYTHON rdbunit.py -e "examples/$i.rdbu" >script.sql ; then
    echo "Script failed" 1>&2
    exit 1
  fi
  if ! sqlite3 <script.sql >script.out ; then
    echo "Sqlite execution failed" 1>&2
    exit 1
  fi
  if egrep -v -e '^ok [0-9]' -e '^[0-9]+\.\.[0-9]+.?$' script.out ; then
    echo "Test failed" 1>&2
    exit 1
  fi
done

rm script.sql script.out
