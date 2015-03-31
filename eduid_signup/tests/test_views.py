import time
from mock import patch
import pymongo
import unittest
from pyramid_sna.compat import urlparse

from webtest import TestApp

from eduid_userdb.testing import MongoTestCase
from eduid_signup import main
from eduid_signup.testing import FunctionalTests, SETTINGS

import pprint
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


class SignupAppTest(MongoTestCase):

    def setUp(self):
        super(SignupAppTest, self).setUp()
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

        # Tell the Celery task where to find the SignupUserDb
        import eduid_am.tasks
        eduid_am.tasks.USERDBS['eduid_signup'] = self.signup_userdb

    def tearDown(self):
        super(SignupAppTest, self).tearDown()
        self.testapp.reset()
        self.signup_userdb.drop_collection()
        self.toudb.consent.drop()


class SNATests(SignupAppTest):
    """
    Tests of the complete signup process using Social Network site
    """

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

    def test_signup_with_good_email_and_then_google(self):
        res = self.testapp.post('/', {'email': 'johnBROWN@example.com'})  # e-mail matching NEW_USER
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('foo')
        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/success/')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        user = self.signup_userdb.get_user_by_pending_mail_address('JOHNbrown@example.com')
        if not user:
            self.fail("User could not be found using pending mail address")
        logger.debug("User in database after e-mail would have been sent:\n{!s}".format(
            pprint.pformat(user.to_dict())
        ))

        # Now, verify the signup process can be completed by the user
        # switching to the Google track instead
        logger.debug("\n\nUser switching to Social signup instead\n\n")

        self._google_login(NEW_USER)

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)  # one user in there, from e-mail signup above

        res2 = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)
        res3 = res2.form.submit('action')

        # Check that the result was a redirect to /sna_account_created/
        self.assertEqual(res3.status, '302 Found')
        self.assertRegexpMatches(res3.location, '/sna_account_created/')

        # Verify there is still one user in the signup userdb
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'
            res4 = self.testapp.get(res3.location)
            logger.debug("RES4 LOC {!r}".format(res4.location))
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

    def _google_login(self, userdata):
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

        self._google_callback(state, userdata)



class SignupEmailTests(SignupAppTest):
    """
    Test of the complete signup process using an e-mail address
    """

    def test_signup_with_good_email(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('foo')
        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/success/')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        user = self.signup_userdb.get_user_by_pending_mail_address('foo@example.com')
        if not user:
            self.fail("User could not be found using pending mail address")
        logger.debug("User in database after e-mail would have been sent:\n{!s}".format(
            pprint.pformat(user.to_dict())
        ))

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'

            # Visit the confirmation LINK to confirm the e-mail address
            verify_link = "/email_verification/{code!s}/".format(code = user.pending_mail_address.verification_code)
            res4 = self.testapp.get(verify_link)
            self.assertEqual(res4.status, '200 OK')
            res4.mustcontain('You can now log in')

    def test_signup_with_existing_email(self):
        res = self.testapp.post('/', {'email': 'johnsmith@example.org'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('')

        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/email_already_registered/')

        # Should NOT have created any new user
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res4 = self.testapp.get(res3.location)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('Email address already in use')

    def test_signup_with_good_email_twice(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('foo')

        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/success/')

        res4 = self.testapp.get(res3.location)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('Account created successfully')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        user1 = self.signup_userdb.get_user_by_pending_mail_address('foo@example.com')
        if not user1:
            self.fail("User could not be found using pending mail address")
        logger.debug("User in database after e-mail would have been sent:\n{!s}".format(
            pprint.pformat(user1.to_dict())
        ))

        logger.debug("\n\nSignup AGAIN\n\n")

        # Sign up again, with same e-mail
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # Should be same number of users in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('')

        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/resend_email_verification/')

        res4 = self.testapp.get(res3.location)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('Email address already in use')

        res5 = res4.form.submit('foo')
        self.assertEqual(res5.status, '302 Found')
        self.assertEqual(res5.location, 'http://localhost/success/')

        # Check that users pending mail address has been updated with a new verification code
        user2 = self.signup_userdb.get_user_by_pending_mail_address('foo@example.com')
        self.assertEqual(user1.user_id, user2.user_id)
        self.assertEqual(user1.pending_mail_address.email, user2.pending_mail_address.email)
        self.assertNotEqual(user1.pending_mail_address.verification_code, user2.pending_mail_address.verification_code)

    def test_signup_with_good_email_and_wrong_code(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('foo')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        # Visit the confirmation page to confirm the e-mail address
        verify_link = "/email_verification/{code!s}/".format(code = 'not-the-right-code-in-link')
        res4 = self.testapp.get(verify_link)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('/verification_code_form/')

        res5 = self.testapp.get('/verification_code_form/')
        self.assertEqual(res5.status, '200 OK')
        res5.mustcontain('verification-code-input')

        res5.form['code'] = 'not-the-right-code-in-form'
        res6 = res5.form.submit('foo')
        self.assertEqual(res6.status, '200 OK')
        logger.debug("BODY:\n{!s}".format(res6.body))

    def test_signup_confirm_using_form(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res2 = self.testapp.get('/trycaptcha/')
        res3 = res2.form.submit('foo')
        self.assertEqual(res3.status, '302 Found')
        self.assertEqual(res3.location, 'http://localhost/success/')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        user = self.signup_userdb.get_user_by_pending_mail_address('foo@example.com')
        if not user:
            self.fail("User could not be found using pending mail address")
        logger.debug("User in database after e-mail would have been sent:\n{!s}".format(
            pprint.pformat(user.to_dict())
        ))

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'

            # Visit the confirmation FORM to confirm the e-mail address
            res5 = self.testapp.get('/verification_code_form/')
            self.assertEqual(res5.status, '200 OK')
            res5.mustcontain('verification-code-input')

            res5.form['code'] = user.pending_mail_address.verification_code
            res6 = res5.form.submit('foo')
            self.assertEqual(res6.status, '200 OK')
            res6.mustcontain('You can now log in')
