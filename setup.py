import os
import sys

from setuptools import setup, find_packages

try:
    from babel.messages import frontend as babel
except ImportError:
    print "Babel is not installed, you can't localize this package"
    cmdclass = {}
else:
    cmdclass = {
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog
    }

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

version = '0.4.5b2'

requires = [
    'eduid_am >= 0.6.0b0, < 0.7.0',
    'vccs_client >= 0.4.1, < 0.5.0',
    'wsgi_ratelimit >= 0.1',
    'eduid_userdb >= 0.0.0, < 0.1.0',

    'pymongo >= 2.8.0, < 3.0.0',
    'pyramid == 1.5.4',
    'pyramid_beaker == 0.8',
    'pyramid_debugtoolbar == 2.3',
    'pyramid_jinja2 == 2.3.3',
    'pyramid_mailer == 0.14',
    'pyramid_tm == 0.11',
    'pyramid_sna == 0.3.1',
    'waitress == 0.8.9',
    'recaptcha-client == 1.0.6',
    'pwgen == 0.4',
    'proquint == 0.1.0',
    'gunicorn == 19.3.0',
]

if sys.version_info[0] < 3:
    # Babel does not work with Python 3
    requires.append('Babel==1.3')


test_requires = [
    'WebTest==1.4.3',
    'mock==1.0.1',
    'eduid_signup_amp>=0.2.9b0',
]


docs_extras = [
    'Sphinx==1.1.3'
]


testing_extras = test_requires + [
    'nose==1.2.1',
    'coverage==3.6',
    'nosexcover==1.0.8',
]

waitress_extras = requires + [
    'waitress==0.8.2',
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
        'waitress': waitress_extras,
    },
    test_suite='eduid_signup',
    entry_points="""\
    [paste.app_factory]
    main = eduid_signup:main
    """,
)
