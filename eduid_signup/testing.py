"""
Funny quirk of running these tests in PyCharm:

  If you, like me, have a project in PyCharm with eduid-signup and all it's dependencies
  'open', and a virtualenv without any of the eduid packages installed, be aware:

  The AM setup will use pkg_resources to find entry points to plugins. Entry points don't
  exist in source code, so you need to build an egg of eduid-signup-amp and put it somewhere
  where it will be found. For me it works to

    $ cd eduid-signup-amp
    $ python setup.py sdist

"""

import unittest

import pymongo

from webtest import TestApp, TestRequest
from pyramid.interfaces import ISessionFactory
from pyramid.security import remember
from pyramid.testing import DummyRequest

from eduid_signup import main
from eduid_userdb.signup import SignupUserDB
from eduid_userdb.testing import MongoTemporaryInstance


MONGO_URI_TEST = 'mongodb://localhost:27017/eduid_signup_test'
MONGO_URI_TEST_AM = 'mongodb://localhost:27017/eduid_am_test'
MONGO_URI_TEST_TOU = 'mongodb://localhost:27017/eduid_tou_test'


SETTINGS = {
    'profile_link': 'http://profiles.example.com/edit',
    'reset_password_link': ' http://profiles.example.com/reset_password',
    'site.name': 'Test Site',
    'auth_tk_secret': '123456',
    'auth_shared_secret': '123123',
    'session.cookie_expires': '3600',
    'mongo_uri': MONGO_URI_TEST,
    'mongo_uri_am': MONGO_URI_TEST_AM,
    'mongo_uri_tou': MONGO_URI_TEST_TOU,
    'tou_version': '2014-v1',
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
    'signup_hostname': 'signup.example.com',
    'signup_baseurl': 'http://signup.example.com',
}


class DBTests(unittest.TestCase):
    """Base TestCase for those tests that need a db configured"""

    clean_dbs = dict()

    def setUp(self):
        try:
            self.signup_userdb = SignupUserDB(SETTINGS['mongo_uri'])
        except pymongo.errors.ConnectionFailure:
            self.signup_userdb = None

    def tearDown(self):
        if not self.signup_userdb:
            return None
        if 'signup_userdb' in self.clean_dbs:
            self.signup_userdb._drop_whole_collection()


class FunctionalTests(DBTests):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        super(DBTests, self).setUp()
        self.tmp_db = MongoTemporaryInstance.get_instance()

        _settings = SETTINGS
        _settings.update({
            'mongo_uri': self.tmp_db.get_uri('eduid_am'),
            })

        # Don't call DBTests.setUp because we are getting the
        # db in a different way
        try:
            app = main({}, **_settings)
            self.testapp = TestApp(app)
            self.signup_userdb = app.registry.settings['signup_db']
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")

    def tearDown(self):
        super(FunctionalTests, self).tearDown()
        self.testapp.reset()

    def set_user_cookie(self, user_id):
        request = TestRequest.blank('', {})
        request.registry = self.testapp.app.registry
        remember_headers = remember(request, user_id)
        cookie_value = remember_headers[0][1].split('"')[1]
        self.testapp.cookies['auth_tkt'] = cookie_value

    def add_to_session(self, data):
        queryUtility = self.testapp.app.registry.queryUtility
        session_factory = queryUtility(ISessionFactory)
        request = DummyRequest()
        session = session_factory(request)
        for key, value in data.items():
            session[key] = value
        session.persist()
        self.testapp.cookies['beaker.session.id'] = session._sess.id
