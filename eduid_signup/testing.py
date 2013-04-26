import unittest

from webtest import TestApp

from eduid_signup import main
from eduid_signup.db import MongoDB

MONGO_URI_TEST = 'mongodb://localhost:27017/eduid_signup_test'


class DBTests(unittest.TestCase):
    """Base TestCase for those tests that need a db configured"""

    clean_collections = tuple()

    def setUp(self):
        mongodb = MongoDB(MONGO_URI_TEST)
        self.db = mongodb.get_database()

    def tearDown(self):
        for collection in self.clean_collections:
            self.db.drop_collection(collection)


class FunctionalTests(DBTests):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        # Don't call DBTests.setUp because we are getting the
        # db in a different way
        settings = {
            'profile_link': 'http://profiles.example.com/edit',
            'site.name': 'Test Site',
            'auth_tk_secret': '123456',
            'mongo_uri': MONGO_URI_TEST,
            'testing': True,
            'jinja2.directories': 'eduid_signup:templates',
            'jinja2.undefined': 'strict',
            'jinja2.i18n.domain': 'eduid_signup',
            'jinja2.filters': """
    route_url = pyramid_jinja2.filters:route_url_filter
    static_url = pyramid_jinja2.filters:static_url_filter
"""
        }
        app = main({}, **settings)
        self.testapp = TestApp(app)
        self.db = app.registry.settings['mongodb'].get_database()

    def tearDown(self):
        super(FunctionalTests, self).tearDown()
        self.testapp.reset()
