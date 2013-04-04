import os

from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()


requires = [
    'pymongo==2.5',
    'pyramid==1.4',
    'pyramid_beaker==0.7',
    'pyramid_debugtoolbar==1.0.4',
    'pyramid_jinja2==1.6',
    'waitress==0.8.2',
]


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
    version='0.1dev',
    description='eduId Sign Up application',
    long_description = README + '\n\n' + CHANGES,
    # TODO: add classifiers
    author='NORDUnet A/S',
    url='https://github.com/SUNET/eduid-signup',
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
