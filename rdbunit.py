#!/usr/bin/env python
#
# SQL Unit Test runner
#
# Copyright 2017 Diomidis Spinellis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Run as:
# python rdbunit.py "leader_commits_nl_comments.rdbu" |
# mysql -u root -p$DBPASS -N
#

import fileinput
import re
import shlex
import sys

# Values and their corresponding SQL data types
re_integer = re.compile(r'\d+$')
re_real = re.compile(r'((\d+\.\d*)|(\d*\.\d+)([Ee]-?\d+)?)|\d+[Ee]-?\d+$')
re_date = re.compile(r'\d{4}-\d\d-\d\d$')
re_time = re.compile(r'\d+:\d+:\d+$')
re_timestamp = re.compile(r'\d{4}-\d\d-\d\d$ \d+:\d+:\d+$')
re_boolean = re.compile(r'(true|false)$', re.IGNORECASE)

include_create = re.compile(r'INCLUDE\s+CREATE\s+(.*)$')
include_select = re.compile(r'INCLUDE\s+SELECT\s+(.*)$')

# Reference to a table in a database \1 is the database \2 is the table name
db_tablespec = re.compile(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)')

# Explicit reference to a table within a specified database
# \1 is the database followed by a .
db_tableref = None

# Created databases
created_databases = []


def create_database(name):
    """Create a database with the specified name"""
    if name in created_databases:
        return
    print('DROP DATABASE IF EXISTS test_' + name + ';')
    print('CREATE DATABASE test_' + name + ';')
    if name != 'default':
        created_databases.append(name)


class SqlType:
    """An SQL type's name and its value representation"""
    def __init__(self, value):
        def boolean_value(v):
            """Return the SQL representation of a Boolean value.
            Use integers for SQLite compatibility."""
            if v.lower() == 'false':
                return '0'
            elif v.lower() == 'null':
                return 'NULL'
            else:
                return '1'

        def quoted_value(v):
            """Return the SQL representation of a quoted value."""
            if v.lower() == 'null':
                return 'NULL'
            else:
                return "'" + v + "'"

        def unquoted_value(v):
            """Return the SQL representation of an unquoted value."""
            if v.lower() == 'null':
                return 'NULL'
            else:
                return str(v)

        if re_integer.match(value):
            self.name = 'INTEGER'
            self.sql_repr = unquoted_value
        elif re_real.match(value):
            self.name = 'REAL'
            self.sql_repr = unquoted_value
        elif re_date.match(value):
            self.name = 'DATE'
            self.sql_repr = quoted_value
        elif re_time.match(value):
            self.name = 'TIME'
            self.sql_repr = quoted_value
        elif re_timestamp.match(value):
            self.name = 'TIMESTAMP'
            self.sql_repr = quoted_value
        elif re_boolean.match(value):
            self.name = 'BOOLEAN'
            self.sql_repr = boolean_value
        else:
            self.name = 'VARCHAR(255)'
            self.sql_repr = quoted_value

    def get_name(self):
        """Return a type's name"""
        return self.name

    def get_value(self, v):
        """Return a type's value, suitably quoted"""
        return self.sql_repr(v)


def create_table(table_name, column_names, values):
    """Create the specified table taking as a hint for types the values.
    Return the type objects associated with the values."""
    print('DROP TABLE IF EXISTS ' + table_name + ';')
    # Create data type objects from the values
    types = map(SqlType, shlex.split(values))
    print('CREATE TABLE ' + table_name + '(' +
          ', '.join(map(lambda n, t: n + ' ' + t.get_name(),
                        column_names, types)) + ');')
    return types

def create_test(test_name, test_input):
    create_database('default')
    print('USE test_default;')
    process_test(test_name, test_input)

def process_sql(file_name, db_re):
    """Process an SQL statement, substituting referenced databases specified
    in the db_re compiled regular expression with the corresponding test one"""
    with open(file_name) as query:
        for line in query:
            line = line.rstrip()
            line = db_re.sub(r'test_\1.', line)
            print(line)

def make_db_re(dbs):
    """Return a compiled regular expression for identifying the
    databases passed in the array"""
    if len(dbs) > 0:
        database_re = r'\b(' + '|'.join(dbs) + r')\.'
        print('-- Database RE: ' + database_re)
    else:
        # This RE cannot match any string
        database_re = r'A\bB'
    return re.compile(database_re, re.IGNORECASE)

def verify_content(number, test_name, case_name):
    """Verify that the specified table has the same content as the
    table test_expected"""
    print("""
        SELECT CASE WHEN
          (SELECT COUNT(*) FROM (
            SELECT * FROM test_expected
            UNION
            SELECT * FROM {}
          ) AS u1) = (SELECT COUNT(*) FROM test_expected) AND
          (SELECT COUNT(*) FROM (
            SELECT * FROM test_expected
            UNION
            SELECT * FROM {}
          ) AS u2) = (SELECT COUNT(*) FROM {})
        THEN 'ok {} - {}: {}' ELSE 'not ok {} - {}: {}' END;\n""".format(
            case_name, case_name, case_name, number, test_name, case_name,
            number, test_name, case_name))

def test_table_name(line):
    """Return the name of the table to used in the test database."""
    m = db_tablespec.match(line)
    if m is not None:
        create_database(m.group(1))
        return 'test_' + line[:-1]
    else:
        return line[:-1]

def insert_values(table, types, line):
    """Insert into the table the specified values and their types coming
    from line"""

    values = shlex.split(line)
    quoted = map(lambda v, t: t.get_value(v), values, types)
    print('INSERT INTO ' + table + ' VALUES (' + ', '.join(quoted) + ');')

def syntax_error(state, line):
    """Terminate the program indicating a syntax error"""
    sys.exit('Syntax error in line: ' + line +
             ' (state: ' + state + ')')

def process_test(test_name, test_spec):
    """Process the specified input stream.
    Return a regular expression matching constructed databases,
    when the postconditions line has been reached."""
    state = 'initial'
    test_number = 1

    for line in test_spec:
        line = line.rstrip()
        if line == '' or line[0] == '#':
            continue

        # Initial state
        if state == 'initial':
            print("\n-- " + line)
            if line == 'BEGIN SETUP':
                state = 'setup'
            elif line == 'BEGIN CREATE':
                db_re = make_db_re(created_databases)
                test_statement_type = 'create'
                state = 'sql'
            elif line == 'BEGIN SELECT':
                print('CREATE VIEW test_select_result AS')
                db_re = make_db_re(created_databases)
                test_statement_type = 'select'
                state = 'sql'
            elif include_select.match(line) is not None:
                m = include_select.match(line)
                print('CREATE VIEW test_select_result AS')
                process_sql(m.group(1), make_db_re(created_databases))
                test_statement_type = 'select'
            elif include_create.match(line) is not None:
                m = include_create.match(line)
                process_sql(m.group(1), make_db_re(created_databases))
                test_statement_type = 'create'
            elif line == 'BEGIN RESULT':
                if test_statement_type == 'select':
                    # Directly process columns; table name is implicit
                    table_name = 'test_select_result'
                    state = 'table_columns'
                    prev_state = 'result'
                elif test_statement_type == 'create':
                    state = 'result'
                else:
                    syntax_error(state, 'CREATE or SELECT not specified')
                test_statement_type = None
            else:
                syntax_error(state, line)

        # Table setup specifications
        elif state == 'setup':
            if line == 'END':
                state = 'initial'
                continue
            # Table name
            if line[-1] == ':':
                table_name = test_table_name(line)
                state = 'table_columns'
                prev_state = 'setup'
                continue
            # Data
            if not table_created:
                types = create_table(table_name, column_names, line)
                table_created = True
            insert_values(table_name, types, line)

        # Embedded SQL code
        elif state == 'sql':
            line = line.rstrip()
            if line == 'END':
                state = 'initial'
                continue
            line = db_re.sub(r'test_\1.', line)
            print(line)

        # Specification of table columns
        elif state == 'table_columns':
            # Table column names
            column_names = line.split()
            state = prev_state
            table_created = False
            continue

        # Check a result
        elif state == 'result':
            if line == 'END':
                verify_content(test_number, test_name, table_name)
                test_number += 1
                state = 'initial'
                continue
            # Table name
            if line[-1] == ':':
                table_name = test_table_name(line)
                state = 'table_columns'
                prev_state = 'result'
                continue
            # Data
            if not table_created:
                types = create_table('test_expected', column_names, line)
                table_created = True
            insert_values('test_expected', types, line)
        else:
            sys.exit('Invalid state: ' + state)
    if state != 'initial':
        sys.exit('Unterminated state: ' + state)

    # Display number of executed test cases
    print('SELECT "1..{}";'.format(test_number - 1))

if __name__ == "__main__":
    print('-- Auto generated test script file from rdbunit')
    if len(sys.argv) > 1:
        for test_script in sys.argv[1:]:
            with open(test_script) as test_input:
                print('-- Input from ' + test_script)
                create_test(test_script, test_input)
    else:
            print('-- Input from stdin')
            create_test('stdin', sys.stdin)
