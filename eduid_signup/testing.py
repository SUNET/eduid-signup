import unittest

from webtest import TestApp

from eduid_signup import main
from eduid_signup.db import MongoDB

import pymongo

MONGO_URI_TEST = 'mongodb://localhost:27017/eduid_signup_test'


class DBTests(unittest.TestCase):
    """Base TestCase for those tests that need a db configured"""

    clean_collections = tuple()

    def setUp(self):
        try:
            mongodb = MongoDB(MONGO_URI_TEST)
            self.db = mongodb.get_database()
        except pymongo.errors.ConnectionFailure:
            self.db = None

    def tearDown(self):
        if not self.db:
            return None
        for collection in self.clean_collections:
            self.db.drop_collection(collection)


class FunctionalTests(DBTests):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        # Don't call DBTests.setUp because we are getting the
        # db in a different way
        settings = {
            'profile_link': 'http://profiles.example.com/edit',
            'reset_password_link': ' http://profiles.example.com/reset_password',
            'site.name': 'Test Site',
            'auth_tk_secret': '123456',
            'auth_shared_secret': '123123',
            'mongo_uri': MONGO_URI_TEST,
            'testing': True,
            'jinja2.directories': 'eduid_signup:templates',
            'jinja2.undefined': 'strict',
            'jinja2.i18n.domain': 'eduid_signup',
            'jinja2.filters': """
    route_url = pyramid_jinja2.filters:route_url_filter
    static_url = pyramid_jinja2.filters:static_url_filter
""",
            'vccs_url': 'http://localhost:8550/',
            'google_client_id': '123',
            'google_client_secret': 'abc',
            'facebook_app_id': '456',
            'facebook_app_secret': 'def',
        }
        try:
            app = main({}, **settings)
            self.testapp = TestApp(app)
            self.db = app.registry.settings['mongodb'].get_database()
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")

    def tearDown(self):
        super(FunctionalTests, self).tearDown()
        self.testapp.reset()
