#!/bin/sh
#
# Test Rdbunit on MariaDB/mySQL
#

# Fail on command errors and unset variables
set -eu

# Run the tests
cd examples
../src/rdbunit/__main__.py --database=mysql *.rdbu |
if [ -n "${MYSQL_ROOT_PASSWORD:-}" ] ; then
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -h 127.0.0.1 -P 3306
else
  sudo mysql -N
fi
