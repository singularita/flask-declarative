#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

"""
Tables
======

Declarative tables backed by SQLSoup query with support for pagination,
sorting and filtering.

.. code-block:: python

    class UserTable(Table):
        query = db.user

        class id(NumericColumn):
            label = _('ID')
            column = db.user.c.id

        class name(TextColumn):
            label = _('Name')
            column = db.user.c.name

        class roles(Column):
            label = _('Roles')
            column = db.user.c.roles

            def search(self, keyword, regex=False):
                terms = re.findall(r'\S+', pattern):
                return self.column.in_(terms)
"""

from collections import OrderedDict
from numbers import Number
from re import findall

from sqlalchemy import and_, or_

from flask import request
from flask_babel import lazy_gettext as _


__all__ = [
    'Table',
    'Column',
    'SingleColumn',
    'TextColumn',
    'NumericColumn',
]


class TableMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases, **kwds):
        return OrderedDict()

    def __new__(cls, name, bases, namespace, **kwds):
        result = type.__new__(cls, name, bases, namespace, **kwds)
        result.column_types = OrderedDict()

        for base in bases:
            if hasattr(base, 'column_types'):
                result.column_types.update(base.column_types)

        for orig_name, Col in list(namespace.items()):
            if isinstance(Col, type) and issubclass(Col, Column):
                name = orig_name
                if orig_name.endswith('_'):
                    name = orig_name[:-1]

                delattr(result, orig_name)

                result.column_types[name] = Col
                Col.name = name

                if Col.label is None:
                    Col.label = Col.name

        return result


class Table(metaclass=TableMeta):
    """
    Parent class for table definitions. Inherit this to create your own table
    types to be instantiated. The base table does not specify any columns.
    """

    query = None
    """
    Base query to build on. You need to override it in the child table types.
    """

    rows = []
    """
    List of row objects that match the requested parameters.
    """

    # DataTables localization messages.
    dt_language = {
        'decimal':        '',
        'emptyTable':     _('No entries found.'),
        'info':           _('Showing _START_ to _END_ of _TOTAL_ entries'),
        'infoEmpty':      _('Showing 0 to 0 of 0 entries'),
        'infoFiltered':   _('(filtered from _MAX_ total)'),
        'infoPostFix':    '',
        'thousands':      ' ',
        'lengthMenu':     _('Show _MENU_ entries'),
        'loadingRecords': _('Loading...'),
        'processing':     _('Processing...'),
        'search':         _('Search:'),
        'zeroRecords':    _('No matching entries found.'),
        'paginate': {
            'first':      _('First'),
            'last':       _('Last'),
            'next':       _('Next'),
            'previous':   _('Previous'),
        },
        'aria': {
            'sortAscending':  _(': activate to sort column ascending'),
            'sortDescending': _(': activate to sort column descending'),
        }
    }

    def __init__(self):
        """
        Upon instantiation, table parameters are loaded from the current
        :attr:`flask.request.args`.
        """

        start, length, value, regex, columns, order = self.parse_request()

        self.columns = OrderedDict()

        for i, (name, Col) in enumerate(self.column_types.items()):
            self.columns[name] = Col(self, columns[i])

        self.total = self.query.count()

        query = self.build_query(order, value, regex)
        self.matching = query.count()
        self.rows = query.offset(start).limit(length).all()

    def build_query(self, order, value, regex=False):
        # XXX: Regex is not supported, I don't know how should it behave
        #      when applied to multiple columns with different types.

        query = self.query
        terms = []

        for column in self.columns.values():
            terms.append(column.filter())

        query = query.filter(and_(*terms))
        terms = []

        for term in findall(r'\S+', value):
            maybe = []

            for column in self.columns.values():
                if column.searchable:
                    maybe.append(column.search(term))

            terms.append(or_(*maybe))

        query = query.filter(and_(*terms))

        ordering = []

        for (column, direction) in order:
            if self.columns[column].orderable:
                column_order = self.columns[column].order(direction)
                ordering += column_order

        query = query.order_by(*ordering)

        return query

    def parse_request(self):
        start = request.args.get('start', 0, type=int)
        length = request.args.get('length', 50, type=int)

        value = request.args.get('search[value]', '')
        regex = request.args.get('search[regex]', False, type=boolean)

        columns = []
        order = []

        for i in range(len(self.column_types)):
            data = request.args.get('columns[{}][data]'.format(i), 0, type=int)
            name = request.args.get('columns[{}][name]'.format(i), 0)

            key = 'columns[{}][searchable]'.format(i)
            searchable = request.args.get(key, True, type=boolean)

            key = 'columns[{}][orderable]'.format(i)
            orderable = request.args.get(key, True, type=boolean)

            key = 'columns[{}][search][value]'.format(i)
            search_value = request.args.get(key, '')

            key = 'columns[{}][search][regex]'.format(i)
            search_regex = request.args.get(key, '', type=boolean)

            columns.append({
                'data': data,
                'name': name,
                'searchable': searchable,
                'orderable': orderable,
                'value': value,
                'regex': regex,
            })

        for i in range(len(self.column_types)):
            key = 'order[{}][column]'.format(i)

            if key not in request.args:
                break

            column = request.args.get(key, 0, type=int)

            if column >= len(self.column_types) or column < 0:
                continue

            key = 'order[{}][dir]'.format(i)
            direction = request.args.get(key, 'asc')

            column = list(self.column_types.keys())[column]
            order.append((column, direction))

        return (start, length, search_value, search_regex, columns, order)

    def json(self):
        """
        Return JSON representation of the table data in a form that is
        compatible with DataTables and also includes some column metadata.
        """

        data = []

        for row in self.rows:
            data.append([])

            for column in self.columns.values():
                data[-1].append(column.extract(row))

        columns = []

        for column in self.columns.values():
            columns.append({
                'name': column.name,
                'label': column.label,
            })

        return {
            'draw': request.args.get('draw', 0, type=int),
            'recordsTotal': self.total,
            'recordsFiltered': self.matching,
            'data': data,
            'columns': columns,
        }


class Column:
    """
    Parent class for column definitions.
    """

    label = None
    """
    Label to use when displaying the column to the user.
    """

    def __init__(self, table, options):
        self.table = table

        self.searchable = options['searchable']
        self.orderable = options['orderable']
        self.filter_value = options['value']
        self.filter_regex = options['regex']

    def order(self, direction):
        """
        Return list of ordering expressions needed to order by this column.
        If the column is composed from multiple values, simply return more
        expressions.

        :param direction: Either ``'asc'`` or ``'desc'`` indicator of the
            sorting other. Other values cause undefined but sane behavior.
        """

        return []

    def filter(self):
        return self.search(self.filter_value, self.filter_regex)

    def search(self, keyword, regex=False):
        """
        Return filter expression to filter by presence of the keyword.

        :param keyword: The keyword to require in the value.
        :param regex: Boolean flag indicating that the keyword is actually a
            regular expression to be matched against.
        """

        return or_()

    def extract(self, row):
        """
        Extract value of the column from the row.
        Uses :func:`getattr` by default.
        """

        return getattr(row, self.name)


class SingleColumn(Column):
    """
    Column type for columns backed by a single database column.
    """

    column = None
    """
    SQLAlchemy column to use for filtering and ordering.
    You need to specify this value for the column to work.
    """

    def order(self, direction):
        if direction == 'asc':
            return [self.column.asc()]

        if direction == 'desc':
            return [self.column.desc()]

        return []


class TextColumn(SingleColumn):
    """
    Column type for simple text-based cells.
    """

    def search(self, keyword, regex=False):
        if regex:
            return self.column.op('~')(keyword)

        return self.column.ilike('%{}%'.format(keyword))


class NumericColumn(SingleColumn):
    """
    Column type for simple number-based cells.
    """

    def search(self, keyword, regex=False):
        try:
            keyword = self.column.type.python_type(keyword)
            return self.column == keyword
        except:
            return or_()


def boolean(val):
    return val == 'true'


# vim:set sw=4 ts=4 et:
