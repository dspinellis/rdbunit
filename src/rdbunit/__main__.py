#!/usr/bin/env python3
#
# Copyright 2017-2023 Diomidis Spinellis
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

# Disable useless object inheritance for compatibility with Python 2

"""
SQL Unit Test runner

Run examples:
python rdbunit.py [-e] leader_commits_nl_comments.rdbu |
mysql -u root -p$DBPASS -N

python rdbunit.py --database=postgresql communication_report.rdbu |
psql -U ght -h 127.0.0.1 -t -q ghtorrent

"""

from __future__ import absolute_import
from __future__ import print_function
import argparse
import os
import re
import shlex
import sys
from pyparsing import (
    Word,
    CaselessKeyword,
    Group,
    delimitedList,
    Optional,
    alphas,
    alphanums
)

# Values and their corresponding SQL data types
RE_INTEGER = re.compile(r'\d+$')
RE_REAL = re.compile(r'((\d+\.\d*)|(\d*\.\d+)([Ee]-?\d+)?)|\d+[Ee]-?\d+$')
RE_DATE = re.compile(r'\d{4}-\d\d-\d\d$')
RE_TIME = re.compile(r'\d+:\d+:\d+$')
RE_TIMESTAMP = re.compile(r'\d{4}-\d\d-\d\d$ \d+:\d+:\d+$')
RE_BOOLEAN = re.compile(r'(true|false)$', re.IGNORECASE)

RE_INCLUDE_CREATE = re.compile(r'INCLUDE\s+CREATE\s+(.*)$')
RE_INCLUDE_SELECT = re.compile(r'INCLUDE\s+SELECT\s+(.*)$')

RE_FULL_CREATE_INDEX = re.compile(r'CREATE\s+INDEX\s+[^;]+;', re.IGNORECASE)
RE_PARTIAL_CREATE_INDEX = re.compile(r'CREATE\s+INDEX\b[^;]*$', re.IGNORECASE)
RE_CLEAR_TO_SEMICOLON = re.compile(r'^[^;]*;')

RE_FULL_ATTACH_DATABASE = re.compile(r'ATTACH\s+[^;]+;', re.IGNORECASE)

# Reference to a table in a database \1 is the database \2 is the table name
RE_DB_TABLESPEC = re.compile(r'([A-Za-z_]\w*)\.([A-Za-z_]\w*)')
# Remove the test_ prefix from a string
RE_NON_TEST = re.compile(r'^test_')


class Database(object):
    """Generic database commands"""
    @staticmethod
    def initialize():
        """Issue engine-specific initialization commands"""
        return

    @staticmethod
    def drop(name):
        """Remove the specified database"""
        # pylint: disable=unused-argument
        return

    @staticmethod
    def use(name):
        """Use by default the specified database"""
        # pylint: disable=unused-argument
        return

    @staticmethod
    def boolean_value(val):
        """Return the SQL representation of a Boolean value."""
        if val.lower() == 'false':
            return 'FALSE'
        if val.lower() == 'null':
            return 'NULL'
        return 'TRUE'


class DatabaseMySQL(Database):
    """SQL-specific commands for MySQL"""
    @staticmethod
    def drop(name):
        """Remove the specified database"""
        print('DROP DATABASE IF EXISTS ' + name + ';')

    @staticmethod
    def create_db(name):
        """Create the specified database"""
        print('CREATE DATABASE ' + name + ';')

    @staticmethod
    def create_view(name):
        """Create the specified view"""
        print('CREATE VIEW ' + name + ' AS')

    @staticmethod
    def use(name):
        """Use by default the specified database"""
        print('USE ' + name + ';')


class DatabasePostgreSQL(Database):
    """SQL-specific commands for PostgreSQL"""
    @staticmethod
    def initialize():
        """Issue engine-specific initialization commands"""
        # Don't show warnings when IF EXISTS doesn't exist
        print("\\set ON_ERROR_STOP true\nSET client_min_messages='ERROR';")

    @staticmethod
    def drop(name):
        """Remove the specified database"""
        print('DROP SCHEMA IF EXISTS ' + name + ' CASCADE;')

    @staticmethod
    def create_db(name):
        """Create the specified database"""
        print('CREATE SCHEMA ' + name + ';')

    @staticmethod
    def create_view(name):
        """Create the specified view"""
        print('CREATE VIEW ' + name + ' AS')

    @staticmethod
    def use(name):
        """Use by default the specified database"""
        print('SET search_path TO ' + name + ';')


class DatabaseSQLite(Database):
    """SQL-specific commands for SQLite"""
    @staticmethod
    def create_db(name):
        """Create the specified database"""
        print('ATTACH DATABASE ":memory:" AS ' + name + ';')

    @staticmethod
    def create_view(name):
        """Create the specified view"""
        print('CREATE TEMP VIEW ' + name + ' AS')

    @staticmethod
    def boolean_value(val):
        """Return the SQL representation of a Boolean value.
        SQLite requires integers."""
        if val.lower() == 'false':
            return '0'
        if val.lower() == 'null':
            return 'NULL'
        return '1'


def create_database(dbengine, created_databases, name):
    """Create a database with the specified name"""
    if name is None or name in created_databases:
        return
    dbengine.drop(name)
    dbengine.create_db(name)
    if name != 'default':
        created_databases.append(name)


class SqlType(object):
    """An SQL type's name and its value representation"""
    def __init__(self, dbengine, value):
        # pylint: disable=too-many-branches
        def boolean_value(val):
            """Return the engine-specific Boolean representation of val."""
            return self.dbengine.boolean_value(val)

        def quoted_value(val):
            """Return the SQL representation of a quoted value."""
            if val.lower() == 'null':
                return 'NULL'
            return "'" + val + "'"

        def unquoted_value(val):
            """Return the SQL representation of an unquoted value."""
            if val.lower() == 'null':
                return 'NULL'
            return str(val)

        self.dbengine = dbengine
        if RE_INTEGER.match(value):
            self.name = 'INTEGER'
            self.sql_repr = unquoted_value
        elif RE_REAL.match(value):
            self.name = 'REAL'
            self.sql_repr = unquoted_value
        elif RE_DATE.match(value):
            self.name = 'DATE'
            self.sql_repr = quoted_value
        elif RE_TIME.match(value):
            self.name = 'TIME'
            self.sql_repr = quoted_value
        elif RE_TIMESTAMP.match(value):
            self.name = 'TIMESTAMP'
            self.sql_repr = quoted_value
        elif RE_BOOLEAN.match(value):
            self.name = 'BOOLEAN'
            self.sql_repr = boolean_value
        else:
            self.name = 'VARCHAR(255)'
            self.sql_repr = quoted_value

    def get_name(self):
        """Return a type's name"""
        return self.name

    def get_value(self, val):
        """Return a type's value, suitably quoted"""
        return self.sql_repr(val)


def create_table(dbengine, table_name, column_names, values, flag_order):
    # pylint: disable=broad-exception-raised
    """Create the specified table taking as a hint for types the values.
    Return the type objects associated with the values."""
    print('DROP TABLE IF EXISTS ' + table_name + ';')
    # Create data type objects from the values
    types = [SqlType(dbengine, x) for x in shlex.split(values)]
    if flag_order == 1:
        print(
            'CREATE TABLE ' + table_name + ' ('
            + ', '.join([
                n + ' ' + t.get_name()
                for n, t in zip(column_names, types)
            ])
            + ');'
        )
    if flag_order == -1:  # execute option for order.
        # not apply for setup, only for reasults table.
        if table_name == 'test_expected':
            # Handle each supporded db diffrently.
            # due to diffrent syntax for auto-increment column.
            # for the CREATE command.
            if 'DatabaseMySQL' in str(dbengine):
                # Add Auto increment internal column for DatabaseMySQL
                error_message = (
                     "BEGIN ORDERED RESULT not supported for "
                     "DatabaseMySQL"
                )

                raise Exception(error_message)
            if 'DatabasePostgreSQL' in str(dbengine):
                # Auto increment internal column for DatabasePostgreSQL
                error_message = (
                     "BEGIN ORDERED RESULT not supported for "
                     "DatabasePostgreSQL"
                )

                raise Exception(error_message)
            if 'DatabaseSQLite' in str(dbengine):
                print('--Auto increment internal column for DatabaseSQLite')
                print(
                    'CREATE TABLE ' + table_name + ' ('
                    + 'rn INTEGER PRIMARY KEY AUTOINCREMENT, '
                    + ', '.join([
                        n + ' ' + t.get_name()
                        for n, t in zip(column_names, types)
                    ])
                    + ');'
                )
        else:  # create set up table.
            print(
                'CREATE TABLE ' + table_name + ' ('
                + ', '.join(
                    [
                        n + ' ' + t.get_name()
                        for n, t in zip(column_names, types)
                    ]
                )
                + ');'
            )
    return types


def create_test_cases(args, test_name, file_input):
    """Create the test cases with the specified name in input"""
    print('-- Input from ' + test_name)
    if args.database == 'mysql':
        dbengine = DatabaseMySQL()
    elif args.database == 'postgresql':
        dbengine = DatabasePostgreSQL()
    elif args.database == 'sqlite':
        dbengine = DatabaseSQLite()
    else:
        sys.exit('Unsupported database: ' + args.database)
    dbengine.initialize()
    if not args.existing_database:
        database_name = os.getenv('ROLAPDB')
        if not database_name:
            database_name = 'test_default'
        create_database(dbengine, [], database_name)
        dbengine.use(database_name)
    process_test(args, dbengine, test_name, file_input)


def process_sql(file_name, db_re):
    """Process an SQL statement, substituting referenced databases specified
    in the db_re compiled regular expression with the corresponding test one"""
    with open(file_name, encoding="UTF-8") as query:
        for line in query:
            line = line.rstrip()

            # Remove index creation and database attachment in single line
            line = re.sub(RE_FULL_CREATE_INDEX, '', line)
            line = re.sub(RE_FULL_ATTACH_DATABASE, '', line)

            # Remove CREATE INDEX statements spanning multiple lines
            if RE_PARTIAL_CREATE_INDEX.search(line) is not None:
                first_part = re.sub(RE_PARTIAL_CREATE_INDEX, '', line)
                last_line = ''
                for query_line in query:
                    # Skip lines as INDEX statment continues
                    if query_line.find(';') == -1:
                        continue
                    last_line = query_line
                    break
                line = first_part + re.sub(RE_CLEAR_TO_SEMICOLON, '',
                                           last_line)

            line = db_re.sub(r'test_\1.', line)
            print(line)


def make_db_re(dbs):
    """Return a compiled regular expression for identifying the
    databases passed in the array"""
    if dbs:
        non_test_dbs = [RE_NON_TEST.sub('', x) for x in dbs]
        database_re = r'\b(' + '|'.join(non_test_dbs) + r')\.'
        print('-- Database RE: ' + database_re)
    else:
        # This RE cannot match any string
        database_re = r'(A\bB)'
    return re.compile(database_re, re.IGNORECASE)


def verify_content(args, number, test_name, case_name):
    """Verify that the specified table has the same content as the
    table test_expected"""
    print(f"""
        SELECT CASE WHEN
          (SELECT COUNT(*) FROM (
            SELECT * FROM test_expected
            UNION
            SELECT * FROM {case_name}
          ) AS u1) = (SELECT COUNT(*) FROM test_expected) AND
          (SELECT COUNT(*) FROM (
            SELECT * FROM test_expected
            UNION
            SELECT * FROM {case_name}
          ) AS u2) = (SELECT COUNT(*) FROM {case_name})""")
    print(f"""THEN 'ok {number} - {test_name}: {case_name}' ELSE
'not ok {number} - {test_name}: {case_name}' END;\n"""
          )
    if args.results:
        print("SELECT 'Result set:';")
        print(f"SELECT * FROM {case_name};")
    if args.compare:
        print("SELECT 'Non expected records in result set:';")
        print(f"SELECT * FROM {case_name} EXCEPT SELECT * FROM test_expected;")
        print("SELECT 'Missing records in result set:';")
        print(f"SELECT * FROM test_expected EXCEPT SELECT * FROM {case_name};")


def test_table_name(line):
    """Return the name of the table to use."""
    matched = RE_DB_TABLESPEC.match(line)
    if matched is not None:
        return 'test_' + line[:-1]
    return line[:-1]


def insert_values(table, types, line, dbengine, flag_order):
    """Insert into the table the specified values and their types coming
    from line"""

    values = shlex.split(line)
    quoted_list = ', '.join([t.get_value(v) for v, t in zip(values, types)])
    # execute based on order && db is SQLite && step 3.
    # Result (exclude insert of setup).
    if (
        flag_order == -1
        and 'DatabaseSQLite' in str(dbengine)
        and table == 'test_expected'
    ):
        # Special handling for SQLite, for autoincrement. Insert NULL.
        print('INSERT INTO ' + table + ' VALUES (' +
              'NULL,' + quoted_list + ');')
    else:
        print('INSERT INTO ' + table + ' VALUES (' + quoted_list + ');')


def syntax_error(line_number, state, reason):
    """Terminate the program indicating a syntax error"""
    sys.exit(f"Syntax error on line {line_number}: {reason}" +
             f" (state: {state})")


def file_to_list(file_input):
    """Convert file input into a list.  This allows it to be processed
    multiple times."""
    result = []
    for line in file_input:
        result.append(line)
    return result


def create_databases(dbengine, test_spec, created_databases):
    """Scan the file for the databases to create and update
    created_databases with their names"""
    for line in test_spec:
        matched = RE_DB_TABLESPEC.match(line)
        if matched is not None:
            create_database(dbengine, created_databases,
                            'test_' + matched.group(1))


def extract_order_by_clauses(sql_text):
    # pylint: disable-msg=too-many-locals
    """Extract the final ORDER BY context"""
    # Define SQL tokens
    order_sql_command = CaselessKeyword("ORDER")
    by_sql_command = CaselessKeyword("BY")
    asc_sql_command = CaselessKeyword("ASC")
    desc_sql_command = CaselessKeyword("DESC")

    # Define a column name (allow alphanumerics and underscores)
    column_name = Word(alphas + "_", alphanums + "_")

    # Define the order term
    # which is a column name followed by optional ASC or DESC
    order_term = Group(
        column_name("column") +
        Optional(asc_sql_command | desc_sql_command,
                 default="ASC")("direction"))

    # Define the full ORDER BY clause
    order_by_clause = (
        order_sql_command
        + by_sql_command
        + Group(
            delimitedList(
                order_term,
                delim=", "
            )
        )("order_by")
    )
    # Parse and extract all ORDER BY clauses
    order_by_matches = order_by_clause.searchString(sql_text)
    results = []
    for match in order_by_matches:
        # Collect the columns and their respective sort orders
        columns_with_order = [(term.column,
                               term.direction) for term in match.order_by]
        results.append(columns_with_order)
    order_by_command = 'ORDER BY'
    for idx, order_by in enumerate(results, start=1):
        for column, direction in order_by:
            if idx == len(results):
                order_by_command = order_by_command + f" {column} {direction},"
        order_by_command = order_by_command[:-1]
    return order_by_command


def process_test(args, dbengine, test_name, test_spec):
    """Process the specified input stream.
    Return a regular expression matching constructed databases,
    when the postconditions line has been reached."""
    # pylint: disable=too-many-statements
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    state = 'initial'
    test_number = 1
    # Created databases
    created_databases = []
    # To silence pylint
    table_created = False
    column_names = []
    # flag for checking the option ordered
    flag_order = None

    test_spec = file_to_list(test_spec)
    if 'BEGIN ORDERED RESULT' in [s.strip() for s in test_spec if s.strip()]:
        flag_order = -1  # execute option for ordered result
    else:
        flag_order = 1  # execute option for not ordered result
    create_databases(dbengine, test_spec, created_databases)
    db_re = make_db_re(created_databases)
    line_number = 0
    for line in test_spec:
        line_number += 1
        line = line.rstrip()
        if line == '' or line[0] == '#':
            continue

        # Initial state
        if state == 'initial':
            print("\n-- " + line)
            if line == 'BEGIN SETUP':
                state = 'setup'
                table_name = None
            elif line == 'BEGIN CREATE':
                test_statement_type = 'create'
                state = 'sql'
            elif line == 'BEGIN SELECT':
                print('CREATE VIEW test_select_result AS')
                test_statement_type = 'select'
                state = 'sql'
            elif RE_INCLUDE_SELECT.match(line) is not None:
                matched = RE_INCLUDE_SELECT.match(line)
                dbengine.create_view('test_select_result')
                process_sql(matched.group(1), make_db_re(created_databases))
                test_statement_type = 'select'
            elif RE_INCLUDE_CREATE.match(line) is not None:
                matched = RE_INCLUDE_CREATE.match(line)
                process_sql(matched.group(1), make_db_re(created_databases))
                test_statement_type = 'create'
            elif line in ('BEGIN RESULT', 'BEGIN ORDERED RESULT'):
                if test_statement_type == 'select':
                    # Directly process columns; table name is implicit
                    table_name = 'test_select_result'
                    state = 'table_columns'
                    prev_state = 'result'
                elif test_statement_type == 'create':
                    state = 'result'
                else:
                    syntax_error(line_number, state,
                                 'CREATE or SELECT not specified')
                test_statement_type = None
            else:
                syntax_error(line_number, state, 'Unknown statement: ' + line)

        # Table setup specifications
        elif state == 'setup':
            if line == 'END':
                state = 'initial'
                table_name = None
                continue
            # Table name
            if line[-1] == ':':
                table_name = test_table_name(line)
                state = 'table_columns'
                prev_state = 'setup'
                continue
            # Data
            if not table_created:
                if not table_name:
                    syntax_error(line_number, state,
                                 'Attempt to provide data ' +
                                 'without specifying a table name')
                types = create_table(dbengine, table_name,
                                     column_names, line, flag_order)
                table_created = True
            insert_values(table_name, types, line, dbengine, flag_order)

        # Embedded SQL code
        elif state == 'sql':
            line = line.rstrip()
            if line == 'END':
                state = 'initial'
                continue
            line = db_re.sub(r'test_\1.', line)
            if flag_order == 1:
                print(line)
            if flag_order == -1:
                if 'ORDER BY' in line:
                    extract_ordered_context = extract_order_by_clauses(line)
                    print(line[0:6]
                          + ' ROW_NUMBER() '
                          + f'OVER({extract_ordered_context}) AS RN,'
                          + line[6:])
                if 'ORDER BY' not in line:
                    print(
                        line[0:6]
                        + ' ROW_NUMBER() OVER(ORDER BY 1) AS RN,'
                        + line[6:]
                    )
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
                if not table_name:
                    syntax_error(line_number, state,
                                 'Attempt to provide data ' +
                                 'without specifying a table name')
                if not table_created:
                    types = create_table(dbengine, 'test_expected',
                                         column_names,
                                         ' '.join(column_names),
                                         flag_order)
                    table_created = True
                verify_content(args, test_number, test_name, table_name)
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
                types = create_table(dbengine, 'test_expected',
                                     column_names, line,
                                     flag_order)
                table_created = True
            insert_values('test_expected', types, line, dbengine, flag_order)
        else:
            sys.exit('Invalid state: ' + state)
    if state != 'initial':
        sys.exit('Unterminated state: ' + state)

    # Display number of executed test cases
    print(f"SELECT '1..{test_number - 1}';")


def main():
    """Program entry point: parse arguments and create test cases"""
    parser = argparse.ArgumentParser(
        description='Relational database query unity testing')
    parser.add_argument('-d', '--database',
                        help='Database engine to use;' +
                        'one of sqlite, mysql, postgresql', default='mysql')

    parser.add_argument('-c', '--compare',
                        help='Compare results of each test with expected ones',
                        action='store_true')

    parser.add_argument('-e', '--existing-database',
                        help='Use existing database; do not create test one',
                        action='store_true')

    parser.add_argument('-r', '--results',
                        help='Show the result of each test',
                        action='store_true')

    parser.add_argument('test_script',
                        help='Script containing test specification',
                        nargs='*', default='-',
                        type=str)
    args = parser.parse_args()
    print('-- Auto generated test script file from rdbunit')
    for script_name in args.test_script:
        if script_name == '-':
            create_test_cases(args, '<stdin>', sys.stdin)
        else:
            with open(script_name, encoding="UTF-8") as test_input:
                create_test_cases(args, script_name, test_input)


if __name__ == "__main__":
    main()
