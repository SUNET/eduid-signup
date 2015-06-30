import time
from mock import patch
import pymongo
import unittest
from pyramid_sna.compat import urlparse

from webtest import TestApp

from eduid_am.testing import MongoTestCase
from eduid_signup import main
from eduid_signup.testing import FunctionalTests, SETTINGS


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

    def test_help_in_swedish(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'sv',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Hem')

    def test_help_in_unknown_language(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'xx',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Help')


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



class SNATests(MongoTestCase):

    def setUp(self):
        # Don't call DBTests.setUp because we are getting the
        # db in a different way
        super(SNATests, self).setUp()
        mongo_settings = {
            'mongo_uri_tou': self.am_settings['MONGO_URI'] + 'tou',
            'tou_version': '2014-v1',
        }   

        if getattr(self, 'settings', None) is None:
            self.settings = mongo_settings
        else:
            self.settings.update(mongo_settings)
        try:
            app = main({}, **SETTINGS)
            self.testapp = TestApp(app)
            self.db = app.registry.settings['mongodb'].get_database()
            self.toudb = app.registry.settings['mongodb_tou'].get_database()
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.db.registered.drop()
        self.toudb.consent.drop()

    def tearDown(self):
        super(SNATests, self).tearDown()
        self.testapp.reset()
        self.db.registered.drop()
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
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        url = urlparse.urlparse(res.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        self._google_callback(state, NEW_USER)

        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.db.registered.find({}).count(), 0)
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(self.db.registered.find({}).count(), 1)
        from eduid_am.db import MongoDB
        with patch.object(MongoDB, 'get_database', clear=True):
            MongoDB.get_database.return_value = self.db
            res = self.testapp.get(res.location)
            time.sleep(0.1)
            self.assertEqual(self.db.registered.find({}).count(), 0)

    def test_google_tou(self):
        # call the login to fill the session
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        url = urlparse.urlparse(res.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        self._google_callback(state, NEW_USER)

        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.toudb.consent.find({}).count(), 0)
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.testapp.get(res.location)
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
        self.assertEqual(self.db.registered.find({}).count(), 0)
        #res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/email_already_registered/')
        self.assertEqual(self.db.registered.find({}).count(), 0)

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
        self.assertEqual(self.db.registered.find({}).count(), 0)
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(self.db.registered.find({}).count(), 1)
