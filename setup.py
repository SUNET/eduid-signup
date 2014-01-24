import os
import sys

from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

version = '0.1dev'

requires = [
    'eduid_am',
    'wsgi_ratelimit',
    'vccs_client==0.3',
    'pymongo==2.5.1',
    'pyramid==1.4.1',
    'pyramid_beaker==0.7',
    'pyramid_debugtoolbar==1.0.4',
    'pyramid_jinja2==1.6',
    'pyramid_mailer==0.11',
    'pyramid_tm==0.7',
    'pyramid_sna==0.2',
    'waitress==0.8.2',
    'recaptcha-client==1.0.6',
    'pwgen==0.4',
    'proquint==0.1.0',
]

if sys.version_info[0] < 3:
    # Babel does not work with Python 3
    requires.append('Babel==1.3')


test_requires = [
    'WebTest==1.4.3',
]


docs_extras = [
    'Sphinx==1.1.3'
]


testing_extras = test_requires + [
    'nose==1.2.1',
    'coverage==3.6',
]


setup(
    name='eduid_signup',
    version=version,
    description='eduID Sign Up application',
    long_description=README + '\n\n' + CHANGES,
    # TODO: add classifiers
    classifiers=[
        # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='identity federation saml',
    author='NORDUnet A/S',
    url='https://github.com/SUNET/eduid-signup',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    tests_require=test_requires,
    extras_require={
        'testing': testing_extras,
        'docs': docs_extras,
    },
    test_suite='eduid_signup',
    entry_points="""\
    [paste.app_factory]
    main = eduid_signup:main
    """,
)
