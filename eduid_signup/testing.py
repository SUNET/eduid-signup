import unittest
from copy import deepcopy

import pymongo

from webtest import TestApp, TestRequest
from pyramid.interfaces import ISessionFactory
from pyramid.security import remember
from pyramid.testing import DummyRequest, DummyResource

from eduid_am.db import MongoDB
from eduid_am import testing as am
from eduid_signup import main


MONGO_URI_TEST = 'mongodb://localhost:%d/signup'
MONGO_URI_TEST_AM = 'mongodb://localhost:%d/am'
MONGO_URI_TEST_TOU = 'mongodb://localhost:%d/tou'


class DBTests(unittest.TestCase):
    """Base TestCase for those tests that need a db configured"""

    clean_collections = tuple()

    def setUp(self):
        self.tmp_db = am.MongoTemporaryInstance.get_instance()
        self.conn = self.tmp_db.conn
        self.port = self.tmp_db.port
        try:
            mongodb = MongoDB(MONGO_URI_TEST % self.port)
            self.db = mongodb.get_database()
        except pymongo.errors.ConnectionFailure:
            self.db = None

    def tearDown(self):
        if not self.db:
            return None
        for collection in self.clean_collections:
            self.db.drop_collection(collection)


SETTINGS = {
    'profile_link': 'http://profiles.example.com/edit',
    'reset_password_link': ' http://profiles.example.com/reset_password',
    'site.name': 'Test Site',
    'signup_hostname': 'signup.example.com',
    'signup_baseurl': 'http://signup.example.com',
    'auth_tk_secret': '123456',
    'auth_shared_secret': '123123',
    'session.cookie_expires': '3600',
    'session.key': 'session',
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
}

def get_settings(port):
    settings = deepcopy(SETTINGS)
    settings['mongo_uri'] = settings['mongo_uri'] % port
    settings['mongo_uri_am'] = settings['mongo_uri_am'] % port
    settings['mongo_uri_tou'] = settings['mongo_uri_tou'] % port
    return settings


class FunctionalTests(DBTests):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        # Don't call DBTests.setUp because we are getting the
        # db in a different way
        self.tmp_db = am.MongoTemporaryInstance.get_instance()
        self.conn = self.tmp_db.conn
        self.port = self.tmp_db.port
        self.settings = get_settings(self.port)
        try:
            app = main({}, **(self.settings))
            self.testapp = TestApp(app)
            self.db = app.registry.settings['mongodb'].get_database()
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
        self.testapp.set_cookie('auth_tkt', cookie_value)

    def dummy_request(self, cookies={}):
        request = DummyRequest()
        request.context = DummyResource()
        request.db = self.db
        request.registry.settings = self.settings
        return request

    def add_to_session(self, data):
        queryUtility = self.testapp.app.registry.queryUtility
        session_factory = queryUtility(ISessionFactory)
        request = self.dummy_request()
        session = session_factory(request)
        for key, value in data.items():
            session[key] = value
        session.persist()
        self.testapp.set_cookie(session_factory._options.get('key'), session._sess.id)
