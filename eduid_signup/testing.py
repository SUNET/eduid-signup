import unittest

import pymongo

from webtest import TestApp, TestRequest
from pyramid.interfaces import ISessionFactory
from pyramid.security import remember
from pyramid.testing import DummyRequest

from eduid_signup import main
from eduid_userdb.signup import SignupUserDB
from eduid_userdb.testing import MongoTemporaryInstance, MongoTestCase

from eduid_am.celery import celery, get_attribute_manager


SETTINGS = {
    'profile_link': 'http://profiles.example.com/edit',
    'reset_password_link': ' http://profiles.example.com/reset_password',
    'site.name': 'Test Site',
    'auth_tk_secret': '123456',
    'auth_shared_secret': '123123',
    'session.cookie_expires': '3600',
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
        self.tmp_db = MongoTemporaryInstance.get_instance()

        _settings = SETTINGS
        _settings.update({
            'mongo_uri': self.tmp_db.get_uri('eduid_signup_test'),
            'mongo_uri_am': self.tmp_db.get_uri('eduid_am_test'),
            'mongo_uri_tou': self.tmp_db.get_uri('eduid_tou_test'),
            })

        self.signup_userdb = SignupUserDB(_settings['mongo_uri'])

        try:
            app = main({}, **_settings)
            self.testapp = TestApp(app)
            self.signup_userdb = app.registry.settings['signup_db']
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")

    def tearDown(self):
        super(FunctionalTests, self).tearDown()
        if not self.signup_userdb:
            return None
        self.signup_userdb._drop_whole_collection()
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
