import time
from mock import patch
import pymongo
import unittest
from pyramid_sna.compat import urlparse

from webtest import TestApp

from eduid_userdb.testing import MongoTestCase
from eduid_signup import main
from eduid_signup.testing import FunctionalTests, SETTINGS

from eduid_am.celery import celery, get_attribute_manager

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
        super(SignupAppTest, self).setUp(celery, get_attribute_manager)
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
        self.signup_userdb._drop_whole_collection()
        self.toudb.consent.drop()

        # Tell the Celery task where to find the SignupUserDb
        import eduid_am.tasks
        eduid_am.tasks.USERDBS['eduid_signup'] = self.signup_userdb

    def tearDown(self):
        super(SignupAppTest, self).tearDown()
        self.testapp.reset()
        self.signup_userdb._drop_whole_collection()
        self.toudb.consent.drop()

    def _start_and_solve_captcha(self, email, check_captcha_post_result=True,
                                 userdb_count=2, signup_userdb_count=0):
        home_post = self.testapp.post('/', {'email': email})
        self.assertEqual(home_post.status, '302 Found')
        self.assertEqual(home_post.location, 'http://localhost/trycaptcha/')

        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), userdb_count)
        self.assertEqual(self.signup_userdb.db_count(), signup_userdb_count)

        captcha_get = self.testapp.get('/trycaptcha/')
        captcha_post = captcha_get.form.submit('foo')
        if check_captcha_post_result:
            self.assertEqual(captcha_post.status, '302 Found')
            self.assertEqual(captcha_post.location, 'http://localhost/success/')

        return captcha_post

    def _get_new_signup_user(self, email):
        signup_user = self.signup_userdb.get_user_by_pending_mail_address(email)
        if not signup_user:
            self.fail("User could not be found using pending mail address")
        logger.debug("User in database after e-mail would have been sent:\n{!s}".format(
            pprint.pformat(signup_user.to_dict())
        ))

        return signup_user

    def _create_account(self, captcha_post):
        res4 = self.testapp.get(captcha_post.location)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('Account created successfully')

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)


class SNATests(SignupAppTest):
    """
    Tests of the complete signup process using Social Network site
    """

    def test_google_signup(self):
        # Verify known starting point (empty ToU database)
        self.assertEqual(self.toudb.consent.find({}).count(), 0)
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        self._google_login(NEW_USER)

        rfi_post = self._review_fetched_info()

        # Verify there is now one user in the signup userdb
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        self._complete_registration(rfi_post)

        # Verify there is now one more user in the central eduid user database
        self.assertEqual(self.amdb.db_count(), 3)
        self.assertEqual(self.signup_userdb.db_count(), 0)
        self.assertEqual(self.toudb.consent.find({}).count(), 1)

    def test_google_existing_user(self):
        self._google_login(EXISTING_USER)

        rfi_get = self._review_fetched_info_get()

        self.assertEqual(rfi_get.location, 'http://localhost/email_already_registered/')
        self.assertEqual(self.signup_userdb.db_count(), 0)

    def test_google_retry(self):
        # call the login to fill the session
        res1 = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        # now, retry
        self._google_login(NEW_USER)

        self._review_fetched_info()

        self.assertEqual(self.signup_userdb.db_count(), 1)

    def test_signup_with_good_email_and_then_google(self):
        captcha_post = self._start_and_solve_captcha(NEW_USER['email'].upper())

        self._create_account(captcha_post)

        self._get_new_signup_user(NEW_USER['email'])

        # Now, verify the signup process can be completed by the user
        # switching to the Social Network (google) track instead
        logger.debug("\n\nUser switching to Social signup instead\n\n")

        self._google_login(NEW_USER)

        rfi_post = self._review_fetched_info(userdb_count=2, signup_userdb_count=1)

        # Verify there is still one user in the signup userdb
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        self._complete_registration(rfi_post)

        # Verify there is now one more user in the central eduid user database
        self.assertEqual(self.amdb.db_count(), 3)

    def test_google_abort(self):
        self._google_login(NEW_USER)

        rfi_get = self._review_fetched_info_get()

        # Simulate clicking the Cancel button
        rfi_post = rfi_get.form.submit('cancel')

        # Check that the result was a redirect to /
        self.assertEqual(rfi_post.status, '302 Found')
        self.assertRegexpMatches(rfi_post.location, 'http://localhost/')

        # Verify no user has been created
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

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

    def _review_fetched_info(self, userdb_count=2, signup_userdb_count=0):
        """
        Perform both the GET and subsequent POST steps of `review_fetched_info'.
        """
        rfi_get = self._review_fetched_info_get(userdb_count=userdb_count,
                                                signup_userdb_count=signup_userdb_count)
        return self._review_fetched_info_post(rfi_get)

    def _review_fetched_info_get(self, userdb_count=2, signup_userdb_count=0):
        # ensure known starting point
        self.assertEqual(self.amdb.db_count(), userdb_count)
        self.assertEqual(self.signup_userdb.db_count(), signup_userdb_count)
        rfi_get = self.testapp.get('/review_fetched_info/')

        self.assertEqual(self.amdb.db_count(), userdb_count)
        self.assertEqual(self.signup_userdb.db_count(), signup_userdb_count)
        return rfi_get

    def _review_fetched_info_post(self, rfi_get):
        rfi_post = rfi_get.form.submit('action')

        # Check that the result was a redirect to /sna_account_created/
        self.assertEqual(rfi_post.status, '302 Found')
        self.assertRegexpMatches(rfi_post.location, '/sna_account_created/')
        return rfi_post

    def _complete_registration(self, rfi_post):
        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'
            res = self.testapp.get(rfi_post.location)
            res.mustcontain('You can now log in')
            for retry in range(3):
                time.sleep(0.1)
                if self.signup_userdb.db_count() == 0:
                    # User was removed from SignupUserDB by attribute manager plugin after
                    # the new user was properly synced to the central UserDB - all done
                    break
            if self.signup_userdb.db_count():
                self.fail('SignupUserDB user count never went back to zero')
        return res


class SignupEmailTests(SignupAppTest):
    """
    Test of the complete signup process using an e-mail address
    """

    def test_signup_with_good_email(self):
        self._start_and_solve_captcha(NEW_USER['email'].upper())

        # Should be one user in the signup_userdb now
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 1)

        user = self._get_new_signup_user(NEW_USER['email'])

        from vccs_client import VCCSClient
        with patch.object(VCCSClient, 'add_credentials', clear=True):
            VCCSClient.add_credentials.return_value = 'faked while testing'

            # Visit the confirmation LINK to confirm the e-mail address
            verify_link = "/email_verification/{code!s}/".format(code = user.pending_mail_address.verification_code)
            res4 = self.testapp.get(verify_link)
            self.assertEqual(res4.status, '200 OK')
            res4.mustcontain('You can now log in')

    def test_signup_with_existing_email(self):
        captcha_post = self._start_and_solve_captcha(EXISTING_USER['email'], check_captcha_post_result=False)

        self.assertEqual(captcha_post.status, '302 Found')
        self.assertEqual(captcha_post.location, 'http://localhost/email_already_registered/')

        # Should NOT have created any new user
        self.assertEqual(self.amdb.db_count(), 2)
        self.assertEqual(self.signup_userdb.db_count(), 0)

        res = self.testapp.get(captcha_post.location)
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Email address already in use')

    def test_signup_with_good_email_twice(self):
        captcha_post = self._start_and_solve_captcha('foo@example.com')

        self._create_account(captcha_post)

        user1 = self._get_new_signup_user('foo@example.com')

        logger.debug("\n\nSignup AGAIN\n\n")

        # Sign up again, with same e-mail
        captcha_post2 = self._start_and_solve_captcha('foo@EXAMPLE.COM',
                                                      check_captcha_post_result=False,
                                                      userdb_count=2,
                                                      signup_userdb_count=1,
                                                      )

        res4 = self.testapp.get(captcha_post2.location)
        self.assertEqual(res4.status, '200 OK')
        res4.mustcontain('Email address already in use')

        res5 = res4.form.submit('foo')
        self.assertEqual(res5.status, '302 Found')
        self.assertEqual(res5.location, 'http://localhost/success/')

        # Check that users pending mail address has been updated with a new verification code
        user2 = self._get_new_signup_user('foo@example.com')
        self.assertEqual(user1.user_id, user2.user_id)
        self.assertEqual(user1.pending_mail_address.email, user2.pending_mail_address.email)
        self.assertNotEqual(user1.pending_mail_address.verification_code, user2.pending_mail_address.verification_code)

    def test_signup_with_good_email_and_wrong_code(self):
        captcha_post = self._start_and_solve_captcha('foo@example.com')

        self._create_account(captcha_post)

        # Visit the confirmation LINK to confirm the e-mail address
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
        captcha_post = self._start_and_solve_captcha('foo@example.com')

        self._create_account(captcha_post)

        user = self._get_new_signup_user('foo@example.com')

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
