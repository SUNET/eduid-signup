import unittest
from copy import deepcopy

import pymongo

from webtest import TestApp, TestRequest
from pyramid.interfaces import ISessionFactory
from pyramid.security import remember
from pyramid.testing import DummyRequest, DummyResource

from eduid_signup import main
from eduid_userdb.signup import SignupUserDB
from eduid_userdb.testing import MongoTestCase

from eduid_am.celery import celery, get_attribute_manager


SETTINGS = {
    'profile_link': 'http://profiles.example.com/edit',
    'reset_password_link': ' http://profiles.example.com/reset_password',
    'site.name': 'Test Site',
    'auth_tk_secret': '123456',
    'auth_shared_secret': '123123',
    'session.cookie_expires': '3600',
    'session.key': 'session',
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


class FunctionalTests(MongoTestCase):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        super(FunctionalTests, self).setUp(celery, get_attribute_manager, userdb_use_old_format=True)

        _settings = deepcopy(SETTINGS)
        _settings.update({
            'mongo_uri': self.tmp_db.get_uri('eduid_signup_test'),
            'mongo_uri_tou': self.tmp_db.get_uri('eduid_tou_test'),
            })
        self.settings.update(_settings)

        try:
            app = main({}, **(self.settings))
            self.testapp = TestApp(app)
            self.signup_userdb = app.registry.settings['signup_db']
            self.toudb = app.registry.settings['mongodb_tou'].get_database()
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")

    def tearDown(self):
        super(FunctionalTests, self).tearDown()
        self.signup_userdb._drop_whole_collection()
        self.amdb._drop_whole_collection()
        self.toudb.consent.drop()
        self.testapp.reset()

    def set_user_cookie(self, user_id):
        request = TestRequest.blank('', {})
        request.registry = self.testapp.app.registry
        remember_headers = remember(request, user_id)
        cookie_value = remember_headers[0][1].split('"')[1]
        self.testapp.cookies['auth_tkt'] = cookie_value

    def dummy_request(self, cookies={}):
        request = DummyRequest()
        request.context = DummyResource()
        request.signup_userdb = self.signup_userdb
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
        self.testapp.cookies[session_factory._options.get('key')] = session._sess.id
