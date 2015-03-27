import time
from mock import patch
import pymongo
import unittest
from pyramid_sna.compat import urlparse

from webtest import TestApp

from eduid_userdb.testing import MongoTestCase
from eduid_signup import main
from eduid_signup.testing import FunctionalTests, SETTINGS

import logging
logger = logging.getLogger(__name__)


EXISTING_USER = {
    'id': '789',
    'name': 'John Smith',
    'given_name': 'John',
    'family_name': 'Smith',
    'email': 'johnsmith@example.com',
    }

NEW_USER = {
    'id': '789',
    'name': 'John Brown',
    'given_name': 'John',
    'family_name': 'Brown',
    'email': 'johnbrown@example.com',
    }


class HomeViewTests(FunctionalTests):

    def test_home(self):
        res = self.testapp.get('/')
        self.assertEqual(res.status, '200 OK')
        res.mustcontain(
            'Welcome to eduID!',
            'Create an account for use with Swedish Universities.',
            'Sign up with your email',
            'Sign up with Facebook',
            'Sign up with Google',
        )

    def test_sign_up_with_bad_email(self):
        res = self.testapp.post('/', {'email': 'a@com'})
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Email is not valid')

    def test_sign_up_with_good_email(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')


class SuccessViewTests(FunctionalTests):

    def test_success(self):
        self.add_to_session({'email': 'mail@example.com'})
        res = self.testapp.get('/success/')
        self.assertEqual(res.status, '200 OK')


class HelpViewTests(FunctionalTests):

    def test_default_language(self):
        res = self.testapp.get('/help/')
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Help')

    def test_help_in_english(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'en',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Help')

    def test_help_in_unknown_language(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'xx',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Help')


class SNATests(MongoTestCase):

    def setUp(self):
        super(SNATests, self).setUp()
        # get the mongo URI for the temporary mongo instance that was just started in MongoTestCase.setup()
        mongo_settings = {
            'mongo_uri': self.mongodb_uri(),
            'mongo_uri_tou': self.mongodb_uri('tou'),
            'tou_version': '2014-v1',
        }

        if getattr(self, 'settings', None) is None:
            self.settings = SETTINGS

        self.settings.update(mongo_settings)
        try:
            _settings = SETTINGS
            _settings.update(self.settings)
            app = main({}, **_settings)
            self.testapp = TestApp(app)
            self.signup_userdb = app.registry.settings['signup_userdb']
            self.toudb = app.registry.settings['mongodb_tou'].get_database()
            logger.info("Unit tests self.signup_userdb: {!s} / {!s}".format(
                self.signup_userdb, self.signup_userdb._coll))
            logger.info("Unit tests self.toudb: {!s}".format(self.toudb))
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.signup_userdb.drop_collection()
        self.toudb.consent.drop()

    def tearDown(self):
        super(SNATests, self).tearDown()
        self.testapp.reset()
        self.signup_userdb.drop_collection()
        self.toudb.consent.drop()

    def _google_callback(self, state, user):

        with patch('requests.post') as fake_post:
            # taken from pyramid_sna
            fake_post.return_value.status_code = 200
            fake_post.return_value.json = lambda: {
                'access_token': '1234',
            }
            with patch('requests.get') as fake_get:
                fake_get.return_value.status_code = 200
                fake_get.return_value.json = lambda: user

                res = self.testapp.get('/google/callback', {
                    'code': '1234',
                    'state': state,
                })

    def test_google(self):
        # call the login to fill the session
        res1 = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        #
        # Check that the result was a redirect to Google OAUTH endpoint
        self.assertEqual(res1.status, '302 Found')
        self.assertRegexpMatches(res1.location, '^https://accounts.google.com/o/oauth2/auth?')
        url = urlparse.urlparse(res1.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        self._google_callback(state, NEW_USER)

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        # Tell the Celery task where to find the SignupUserDb
        import eduid_am.tasks
        eduid_am.tasks.USERDBS['eduid_signup'] = self.signup_userdb
        res2 = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)
        res3 = res2.form.submit('action')

        # Check that the result was a redirect to XXX
        self.assertEqual(res3.status, '302 Found')
        self.assertRegexpMatches(res3.location, '/sna_account_created/')

        # Verify there is now one user in the signup userdb
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'
            res4 = self.testapp.get(res3.location)
            for retry in range(3):
                time.sleep(0.1)
                if self.signup_userdb.db_count() == 0:
                    # User was removed from SignupUserDB by attribute manager plugin after
                    # the new user was properly synced to the central UserDB - all done
                    break
            if self.signup_userdb.db_count():
                self.fail('SignupUserDB user count never went back to zero')

        # Verify there is now one more user in the central eduid user database
        self.assertEqual(self.amdb.db_count(), 3)

    def test_google_tou(self):
        # call the login to fill the session
        res1 = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        #
        # Check that the result was a redirect to Google OAUTH endpoint
        self.assertEqual(res1.status, '302 Found')
        url = urlparse.urlparse(res1.location)
        self.assertRegexpMatches(res1.location, '^https://accounts.google.com/o/oauth2/auth?')
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        # Fake Google OAUTH response
        self._google_callback(state, NEW_USER)

        # The user reviews the information eduid got from Google
        res2 = self.testapp.get('/review_fetched_info/')
        self.assertEqual(res2.status, '200 OK')

        # Verify known starting point (empty ToU database)
        self.assertEqual(self.toudb.consent.find({}).count(), 0)

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'
            # The user presses OK and a new eduid user should be created
            res3 = res2.form.submit('action')
            self.assertEqual(res3.status, '302 Found')
            self.assertRegexpMatches(res3.location, '/sna_account_created/')
            self.testapp.get(res3.location)
            #
            # Verify the users consent of the ToU is registered
            self.assertEqual(self.toudb.consent.find({}).count(), 1)

    def test_google_existing_user(self):
        # call the login to fill the session
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        url = urlparse.urlparse(res.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        self._google_callback(state, EXISTING_USER)

        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.signup_userdb.db_count(), 0)
        #res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/email_already_registered/')
        self.assertEqual(self.signup_userdb.db_count(), 0)

    def test_google_retry(self):
        # call the login to fill the session
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        url = urlparse.urlparse(res.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        self._google_callback(state, NEW_USER)

        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.signup_userdb.db_count(), 0)
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(self.signup_userdb.db_count(), 1)
