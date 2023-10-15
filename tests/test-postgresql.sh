#!/bin/sh
#
# Test Rdbunit on PostgreSQL
#

# Fail on command errors and unset variables
set -eu

if [ -z "${POSTGRES_USER:-}" ] ; then
  export PGPASSWORD=$(openssl rand -base64 21)

  # Setup a PostgreSQL database for testing Rdbunit
  cat <<EOF | sudo -u postgres psql -U postgres >/dev/null
DROP DATABASE IF EXISTS rdbunit_db;
DROP ROLE IF EXISTS rdbunit_user;
CREATE DATABASE rdbunit_db;
CREATE USER rdbunit_user;
GRANT ALL PRIVILEGES ON DATABASE rdbunit_db TO rdbunit_user;
ALTER USER rdbunit_user WITH PASSWORD '$PGPASSWORD';
EOF
fi


# Run the tests
cd examples
for i in *.rdbu ; do
  ../src/rdbunit/__main__.py --database=postgresql $i |
  if [ -n "${POSTGRES_USER:-}" ] ; then
    psql -U "$POSTGRES_USER" -h 127.0.0.1 -p 5432 -t -q
  else
    psql -U rdbunit_user -d rdbunit_db -h localhost -t -q
  fi
done
