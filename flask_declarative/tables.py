#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

"""
Tables
======

Declarative tables backed by SQLSoup query with support for pagination,
sorting and filtering.

.. code-block:: python

    @app.route('/table/data', methods=['POST'])
    def table_data():
        q = db.session.query(db.document.year,
                             db.document.summary,
                             db.document.total)
        return jsonify(dt_json(q, request.json))
"""

from numbers import Number
from re import findall

from sqlalchemy import and_, or_
from sqlalchemy.types import NullType

from flask import request
from flask_babel import format_currency, lazy_gettext as _


__all__ = [
    'dt_json',
    'dt_query',
    'dt_language',
]


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
"""
DataTables localization messages for your convenience.
"""


def dt_json(base, request):
    """
    Uses :func:`dt_query` to query the database and return an
    appropriate representation of the result for the DataTables client.

    Applies the ``offset`` and ``limit`` constraints.

    :param base: Base SQLAlchemy query to augment with request data.
    :param request: JSON object with the request data, usually taken
        straight from :attr:`flask.request.json`.
    """

    start = request['start']
    length = request['length']

    query = dt_query(base, request)
    data = []

    for row in query.offset(start).limit(length).all():
        data.append({})

        for column in query.column_descriptions:
            data[-1][column['name']] = getattr(row, column['name'])

    return {
        'draw': request['draw'],
        'recordsTotal': base.count(),
        'recordsFiltered': query.count(),
        'data': data,
    }


def dt_query(base, request):
    """
    Extend the base query so that it satisfies given DataTables request.

    Please keep in mind that numeric query columns are always matched
    using the ``=`` and textual columns using the ``ILIKE`` or ``~``
    (regex) operator. For this to work correctly, data types of the base
    query columns must be known beforehand. If you use a function or other
    construct that does not impliciate a specific result type, annotate
    it by calling :func:`~sqlalchemy.sql.expression.type_coerce` or
    :func:`~sqlalchemy.sql.expression.cast`.

    Does not include the ``offset`` and ``limit`` constraints.
    These need to be applied separately.

    :param base: Base SQLAlchemy query to augment with data from
       :attr:`flask.request.json`.
    """

    # Gather introspected column objects.
    cdefs = {}

    for column in base.column_descriptions:
        assert column['name'] is not None, \
            'One of the columns has no name. Use label() to name it.'

        assert not isinstance(column['expr'].type, NullType), \
            'Column {!r} is of an unknown type. Use type_coerce().' \
            .format(column['name'])

        cdefs[column['name']] = column['expr']

    query = base
    terms = []

    for column in request['columns']:
        if column['data'] not in cdefs:
            continue

        cdef = cdefs[column['data']]
        value = column['search']['value']
        regex = column['search']['regex']

        terms.append(search(cdef, value, regex))

    query = query.filter(and_(*terms))
    terms = []

    regex = request['search']['regex']
    value = request['search']['value']

    for word in findall(r'\S+', value):
        maybe = []

        for column in request['columns']:
            if not column['searchable']:
                continue

            if not column['data'] in cdefs:
                continue

            cdef = cdefs[column['data']]
            maybe.append(search(cdef, word, regex))

        terms.append(or_(*maybe))

    query = query.filter(and_(*terms))
    ordering = []

    for order in request['order']:
        try:
            if not request['columns'][order['column']]['orderable']:
                continue

            cdef = cdefs[request['columns'][order['column']]['data']]
        except:
            continue

        if order['dir'] == 'asc':
            ordering.append(cdef.asc())
        else:
            ordering.append(cdef.desc())

    query = query.order_by(*ordering)

    return query


def search(cdef, value, regex=False):
    ctype = cdef.type.python_type

    if issubclass(ctype, Number):
        try:
            return cdef == ctype(value)
        except:
            pass
    elif issubclass(ctype, str):
        if regex:
            return cdef.op('~')(value)
        else:
            return cdef.ilike('%{}%'.format(value))
    elif issubclass(ctype, list):
        ctype = cdef.type.item_type.python_type

        try:
            # This is not ideal, but I have no idea on how to match
            # array elements better, for example using ILIKE.
            return cdef.op('&&')([ctype(value)])
        except:
            pass

    return or_()


# vim:set sw=4 ts=4 et:
