#  RDBUnit: Unit testing for relational database queries 

[![Build Status](https://travis-ci.org/dspinellis/rdbunit.svg?branch=master)](https://travis-ci.org/dspinellis/rdbunit)

**RDBUnit** is a unit testing framework for relational database queries.
It allows you to express in a simple way the setup prior to a query,
the query, and the expected results.
RDBUnit can test `SELECT` queries as well as queries that are used
for creating tables and views.
Both types of queries can be either embedded into the test script, or
they can be included from an external file.
The tables for the input and the expected results can be created with
minimal ceremony: RDBUnit will automatically infer the types of the
tables' fields.
