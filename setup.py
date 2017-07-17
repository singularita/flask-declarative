#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from sphinx.setup_command import BuildDoc


name = 'Flask-Declarative'
version = '0.1.0'


def read_requires(path=None):
    from os.path import dirname, join

    if path is None:
        path = join(dirname(__file__), 'requirements.txt')
        print(path)

    with open(path) as fp:
        return [l.strip() for l in fp.readlines()]


setup(**{
    'name': name,
    'version': version,
    'author': 'Singularita s.r.o.',
    'description': 'Declarative components for Flask',
    'license': 'MIT',
    'keywords': 'utilities',
    'url': 'http://github.com/singularita/flask-declarative/',
    'packages': find_packages(),
    'zip_safe': False,
    'classifiers': [
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
    ],
    'install_requires': read_requires(),
    'cmdclass': {
        'doc': BuildDoc,
    },
    'command_options': {
        'doc': {
            'project': ('setup.py', name),
            'version': ('setup.py', version),
            'release': ('setup.py', version),
        },
    },
})


# vim:set sw=4 ts=4 et:
