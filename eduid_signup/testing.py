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
from copy import deepcopy

from webtest import TestApp, TestRequest
from pyramid.interfaces import ISessionFactory
from pyramid.security import remember
from pyramid.testing import DummyRequest, DummyResource

from eduid_signup import main
from eduid_userdb.testing import MongoTestCase
from eduid_userdb.exceptions import MongoConnectionError

from eduid_am.celery import celery, get_attribute_manager


SETTINGS = {
    'profile_link': 'http://profiles.example.com/edit',
    'reset_password_link': ' http://profiles.example.com/reset_password',
    'site_name': 'Test Site',
    'auth_shared_secret': '123123',
    'session_cookie_expires': '3600',
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
    'dashboard_link': 'http://dashboard.example.com',
    'student_link': 'http://eduid.se/privacy.html',
    'technicians_link': 'http://eduid.se/privacy.html',
    'staff_link': 'http://eduid.se/privacy.html',
    'faq_link': 'http://eduid.se/privacy.html',
    'privacy_link': 'http://eduid.se/privacy.html',
    'lang_cookie_domain': 'test.example.edu',
}


class FunctionalTests(MongoTestCase):
    """Base TestCase for those tests that need a full environment setup"""

    def setUp(self):
        super(FunctionalTests, self).setUp(celery, get_attribute_manager, userdb_use_old_format=True)

        _settings = deepcopy(SETTINGS)
        _settings.update({
            'mongo_uri': self.tmp_db.get_uri('eduid_signup_test'),
            })
        self.settings.update(_settings)

        try:
            app = main({}, **(self.settings))
            self.testapp = TestApp(app)
            self.signup_userdb = app.registry.settings['signup_db']
            self.toudb = app.registry.settings['mongodb_tou'].get_database()
        except MongoConnectionError:
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

    def signupconfig_set(self, key, value):
        """
        Update a SignupConfig setting for the app.

        :param key: Configuration parameter to update
        :param value: New value
        :return: None
        """
        self.testapp.app.registry.settings['signupconfig']._cache[key] = value
