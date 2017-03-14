#!/usr/bin/env python

import fileinput
import re
import shlex
import sys

# Values and their corresponding SQL data types
re_integer = re.compile(r'\d+$')
re_real = re.compile(r'((\d+\.\d*)|(\d*\.\d+)([Ee]-?\d+)?)|\d+[Ee]-?\d+$')
re_date = re.compile(r'\d{4}-\d\d-\d\d$')
re_time = re.compile(r'\d+:\d+:\d+$')
re_timestampe = re.compile(r'\d{4}-\d\d-\d\d$ \d+:\d+:\d+$')
re_boolean = re.compile(r'(true|false)$', re.IGNORECASE)

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

def quote(values):
    """Quote the non-digit values in values"""
    ret = []
    for v in values:
        if re_integer.match(v) or re_real.match(v):
            ret.append(v)
        else:
            ret.append("'" + v + "'")
    return ret

def data_type(values):
    """Return the data types corresponding to the values"""
    ret = []
    for v in values:
        if re_integer.match(v):
            ret.append('INTEGER')
        elif re_real.match(v):
            ret.append('REAL')
        elif re_date.match(v):
            ret.append('DATE')
        elif re_time.match(v):
            ret.append('TIME')
        elif re_timestamp.match(v):
            ret.append('TIMESTAMP')
        elif re_boolean.match(v):
            ret.append('BOOLEAN')
        else:
            ret.append('VARCHAR(255)')
    return ret

def create_table(table_name, column_names, values):
    """Create the specified table taking as a hint for types the values"""
    print('DROP TABLE IF EXISTS ' + table_name + ';')
    types = data_type(shlex.split(values))
    print('CREATE TABLE ' + table_name + '(' +
          ', '.join(map(lambda n, t: n + ' ' + t, column_names, types)) + ');')

def create_test(test_script, query):
    create_database('default')
    print('USE test_default;')
    with open(test_script) as test_spec:
        db_re = process_preconditions(test_spec)
        process_query(query, db_re)
        process_postconditions(test_spec)

def process_query(file_name, db_re):
    """Process an SQL query, substituting referenced databases specified
    in the db_re compiled regular expression with the corresponding test one"""
    print('-- Query ' + file_name)
    with open(file_name) as query:
        for line in query:
            line = line.rstrip()
            line = db_re.sub(r'test_\1.', line)
            print(line)

def process_preconditions(test_spec):
    """Process the preconditions of the specified input stream.
    Return a regular expression matching constructed databases,
    when the postconditions line has been reached."""
    print('-- Preconditions')
    state = None
    for line in test_spec:
        line = line.rstrip()
        if line == '' or line[0] == '#':
            continue

        if line == 'POST':
            database_re = r'\b(' + '|'.join(created_databases) + r')\.'
            print('-- Database RE: ' + database_re)
            return re.compile(database_re, re.IGNORECASE)

        # Enter precondition state
        if line == 'PRE':
            state = 'pre'
            continue

        # Table name
        if state == 'pre' and line[-1] == ':':
            state = 'table_columns'
            m = db_tablespec.match(line)
            if m is not None:
                create_database(m.group(1))
                table_name = 'test_' + line[:-1]
            else:
                table_name = line[:-1]
            continue

        # Table column names
        if state == 'table_columns':
            column_names = line.split()
            state = 'pre'
            table_created = False
            continue

        if state == 'pre' and not table_created:
            create_table(table_name, column_names, line)
            table_created = True

        if state == 'pre':
            print('INSERT INTO ' + table_name + ' VALUES (' +
                  ', '.join(quote(shlex.split(line))) + ');')

def verify_content(name):
    """Verify that the specified table has the same content as the
    table expected"""
    print("""
        SELECT CASE WHEN
          (SELECT COUNT(*) FROM (
            SELECT * FROM expected
            UNION
            SELECT * FROM """ + name + """
          ) as u) = (SELECT COUNT(*) FROM expected)
        THEN 'pass' ELSE 'fail' END;
    """)

def process_postconditions(test_spec):
    """Process the postconditions of the specified input stream.
    Ensure that each specified table has the expected content
    by verifying that each specified row exists in it and that the
    number of specified rows is equal to the number of rows in the
    table."""
    print('-- Postconditions')
    state = 'post'
    table_name = ''
    for line in test_spec:
        line = line.rstrip()
        if line == '' or line[0] == '#':
            continue

        # Table name
        if state == 'post' and line[-1] == ':':
            if table_name != '':
                verify_content(table_name)
            state = 'table_columns'
            m = db_tablespec.match(line)
            if m is not None:
                table_name = 'test_' + line[:-1]
            else:
                table_name = line[:-1]
            continue

        # Table column names
        if state == 'table_columns':
            column_names = line.split()
            state = 'post'
            table_created = False
            continue

        if state == 'post' and not table_created:
            create_table('expected', column_names, line)
            table_created = True

        if state == 'post':
            print('INSERT INTO expected VALUES (' +
                  ', '.join(quote(shlex.split(line))) + ');')
            continue
    verify_content(table_name)



if __name__ == "__main__":
    create_test(sys.argv[1], sys.argv[2])
