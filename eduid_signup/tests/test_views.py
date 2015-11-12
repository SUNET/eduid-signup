import time
from mock import patch
from pyramid_sna.compat import urlparse

from eduid_signup.testing import FunctionalTests

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

    def test_home(self):
        res = self.testapp.get('/')
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Welcome to eduID')

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

    def test_success_no_email(self):
        res = self.testapp.get('/success/')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/')

    def test_favicon(self):
        res = self.testapp.get('/favicon.ico')
        self.assertEqual(res.status, '302 Found')

    def test_resend_verification(self):
        self.add_to_session({'email': 'mail@example.com'})
        res = self.testapp.post('/resend_email_verification/')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/success/')

    def test_resend_verification_get(self):
        self.add_to_session({'email': 'mail@example.com'})
        res = self.testapp.get('/resend_email_verification/')
        self.assertEqual(res.status, '200 OK')


class HelpViewTests(FunctionalTests):

    def test_default_language(self):
        res = self.testapp.get('/help/')
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Frequently Asked Questions')

    def test_help_in_english(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'en',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Frequently Asked Questions')

    def test_help_in_swedish(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'sv',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Vart kan jag')

    def test_help_in_unknown_language(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'xx',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Frequently Asked Questions')


class SignupAppTest(FunctionalTests):

    def setUp(self):
        super(SignupAppTest, self).setUp()

        from eduid_signup import views
        mock_config = {
            'return_value': ('x', 'y'),
        }
        self.patcher = patch.object(views, 'generate_password', **mock_config)
        self.patcher.start()

    def tearDown(self):
        super(SignupAppTest, self).tearDown()
        self.patcher.stop()

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
        user = self.amdb.get_user_by_mail(NEW_USER['email'])
        self.assertTrue(user.tou.has_accepted(self.settings['tou_version']))

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

    def test_google_bad_request(self):
        # call the login to fill the session
        self._google_login(NEW_USER)

        self.add_to_session({'dummy': 'dummy'})
        res = self.testapp.get('/review_fetched_info/', status=400)
        self.assertEqual(self.signup_userdb.db_count(), 0)

    def test_google_cancel(self):
        # call the login to fill the session
        self._google_login(NEW_USER)

        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.signup_userdb.db_count(), 0)
        res = res.form.submit('cancel')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(self.signup_userdb.db_count(), 0)
        self.assertEqual(res.location, 'http://localhost/')

    def test_google_tou(self):
        # call the login to fill the session
        self._google_login(NEW_USER)

        res = self.testapp.get('/review_fetched_info/')
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.testapp.get(res.location)
        user = self.amdb.get_user_by_mail(NEW_USER['email'])
        self.assertTrue(user.tou.has_accepted(self.settings['tou_version']))

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

        res5.forms[0]['code'] = 'not-the-right-code-in-form'
        res6 = res5.forms[0].submit('foo')
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

            res5.forms[0]['code'] = user.pending_mail_address.verification_code
            res6 = res5.forms[0].submit('foo')
            self.assertEqual(res6.status, '200 OK')
            res6.mustcontain('You can now log in')


class MockCapchaTests(FunctionalTests):

    mock_users_patches = []

    def setUp(self):
        super(MockCapchaTests, self).setUp()

        from eduid_signup.views import captcha
        class MockCaptcha:
            is_valid = True
        mock_config = {
            'return_value': MockCaptcha(),
        }
        self.patcher_captcha = patch.object(captcha, 'submit', **mock_config)
        self.patcher_captcha.start()

        from eduid_signup.vccs import vccs_client
        class MockClient:
            def add_credentials(self, *args, **kwargs):
                return True
        mock_config2 = {
            'return_value': MockClient(),
        }
        self.patcher_vccs = patch.object(vccs_client, 'VCCSClient', **mock_config2)
        self.patcher_vccs.start()

    def tearDown(self):
        super(MockCapchaTests, self).tearDown()
        self.patcher_captcha.stop()
        self.patcher_vccs.stop()

    def _start_registration(self, email='foo@example.com'):
        res = self.testapp.post('/', {'email': email})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')
        res = self.testapp.get(res.location)
        self.assertEqual(self.signup_userdb.db_count(), 0)
        res = res.form.submit()
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/success/')
        self.assertEqual(self.signup_userdb.db_count(), 1)
        registered = self.signup_userdb.get_user_by_pending_mail_address(email)
        self.assertEqual(registered.pending_mail_address.is_verified, False)
        return registered

    def _complete_registration(self, email='foo@example.com'):
        registered = self._start_registration(email=email)
        code = registered.pending_mail_address.verification_code
        url = 'http://localhost/email_verification/%s/' % code
        res = self.testapp.get(url)
        self.assertEqual(res.status, '200 OK')
        new_user = self.amdb.get_user_by_mail(email)
        return new_user

    def test_set_invalid_method(self):
        self.add_to_session({'email': 'mail@example.com'})
        res = self.testapp.delete('http://localhost/trycaptcha/', status=405)
        self.assertEqual(res.status, '405 Method Not Allowed')

    def test_set_language(self):
        res = self.testapp.get('http://localhost/set_language/?lang=sv')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://signup.example.com')
        res = self.testapp.get(res.location)
        self.assertIn('eller avbryta den avsedda', res.body)

    def test_set_language_invalid_lang(self):
        res = self.testapp.get('http://localhost/set_language/?lang=gr', status=404)
        self.assertEqual(res.status, '404 Not Found')

    def test_404(self):
        res = self.testapp.get('http://localhost/ho-ho-ho/', status=404)
        self.assertEqual(res.status, '404 Not Found')

    def test_start_registration(self):
        self._start_registration()
        new_user = self.amdb.get_user_by_mail('foo@example.com', raise_on_missing=False)
        self.assertEqual(new_user, None)

    def test_email_verification_link(self):
        new_user = self._complete_registration()
        self.assertEqual(new_user.mail_addresses.primary.email, 'foo@example.com')
        self.assertEqual(new_user.mail_addresses.primary.is_verified, True)

    def test_email_verification_link_already_verified(self):
        registered = self._start_registration()
        registered.pending_mail_address.is_verified = True
        self.signup_userdb.save(registered, check_sync=False)
        code = registered.pending_mail_address.verification_code
        url = 'http://localhost/email_verification/%s/' % code
        res = self.testapp.get(url)
        self.assertEqual(res.status, '200 OK')
        self.assertIn('Email address has already been verified', res.body)

    def test_email_verification_code_form(self):
        registered = self._start_registration()
        code = registered.pending_mail_address.verification_code
        res = self.testapp.get('http://localhost/verification_code_form/')
        res.forms[0]['code'] = code
        res = res.forms[0].submit()
        self.assertEqual(res.status, '200 OK')
        new_user = self.amdb.get_user_by_mail('foo@example.com')
        self.assertEqual(new_user.mail_addresses.primary.email, 'foo@example.com')
        self.assertEqual(new_user.mail_addresses.primary.is_verified, True)

    def test_email_verification_code_form_already_verified(self):
        registered = self._start_registration()
        registered.pending_mail_address.is_verified = True
        self.signup_userdb.save(registered, check_sync=False)
        code = registered.pending_mail_address.verification_code
        res = self.testapp.get('http://localhost/verification_code_form/')
        res.forms[0]['code'] = code
        res = res.forms[0].submit()
        self.assertEqual(res.status, '200 OK')
        self.assertIn('Email address has already been verified', res.body)


    def test_email_verification_code_form_invalid_code(self):
        res = self.testapp.get('http://localhost/verification_code_form/')
        res.forms[0]['code'] = 'xxx'
        res = res.forms[0].submit()
        self.assertEqual(res.status, '200 OK')
        self.assertIn('The provided code could not be found', res.body)

    def test_email_verification_link_invalid_code(self):
        url = 'http://localhost/email_verification/%s/' % 'xxx'
        res = self.testapp.get(url)
        self.assertEqual(res.status, '200 OK')
        self.assertIn('There was a problem with the provided code', res.body)

    def test_no_email(self):
        res = self.testapp.post('/', {})
        self.assertEqual(res.status, '200 OK')

    def test_no_email_in_session(self):
        res = self.testapp.post('/', {'email': 'foo@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')
        res = self.testapp.get(res.location)
        self.assertEqual(self.signup_userdb.db_count(), 0)
        self.add_to_session({'dummy': 'dummy'})
        res = res.form.submit()
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/')
        self.assertEqual(self.signup_userdb.db_count(), 0)

    def test_email_exists(self):
        res = self.testapp.post('/', {'email': 'johnsmith@example.com'})
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/trycaptcha/')
        self.assertEqual(self.signup_userdb.db_count(), 0)
        res = self.testapp.get(res.location)
        res = res.form.submit()
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/email_already_registered/')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '200 OK')
        self.assertEqual(self.signup_userdb.db_count(), 0)

    def test_celery_error(self):
        from eduid_am.tasks import update_attributes_keep_result
        class MockAttrManager:
            def get(*args, **kwargs):
                raise Exception('ho')
        mock_config = {
            'return_value': MockAttrManager(),
        }
        with patch.object(update_attributes_keep_result,
                          'delay', **mock_config):
            registered = self._start_registration()
            code = registered.pending_mail_address.verification_code
            url = 'http://localhost/email_verification/%s/' % code
            res = self.testapp.get(url)
            self.assertEqual(res.status, '302 Found')
            self.assertEqual(res.location, 'http://localhost/')
            registered = self.signup_userdb.get_user_by_mail('foo@example.com')
            registered_central = self.amdb.get_user_by_mail('foo@example.com', raise_on_missing=False)
            self.assertEqual(registered_central, None)
            # XXX Should this be verified?
            self.assertEqual(registered.pending_mail_address, None)
            self.assertEqual(registered.mail_addresses.primary.email, 'foo@example.com')
            self.assertEqual(registered.mail_addresses.primary.is_verified, True)

    def test_captcha_url_error(self):
        from eduid_signup.views import captcha
        from urllib2 import URLError
        def side_effect(*args, **kwargs):
            raise URLError('ho')
        mock_config = {
            'side_effect': side_effect,
        }
        with patch.object(captcha, 'submit', **mock_config):
            res = self.testapp.post('/', {'email': 'foo@example.com'})
            self.assertEqual(res.status, '302 Found')
            self.assertEqual(res.location, 'http://localhost/trycaptcha/')
            res = self.testapp.get(res.location)
            self.assertEqual(self.signup_userdb.db_count(), 0)
            from urllib2 import URLError
            self.assertRaises(URLError, res.form.submit)


class MockInvalidCaptchaTest(FunctionalTests):

    def test_captcha_invalid_error(self):
        self.testapp.app.registry.settings['recaptcha_public_key'] = 'key'
        from eduid_signup.views import captcha
        class MockCaptcha:
            is_valid = False
            error_code = 'invalid'
        mock_config = {
            'return_value': MockCaptcha(),
        }
        with patch.object(captcha, 'submit', **mock_config):
            res = self.testapp.post('/', {'email': 'foo@example.com'})
            self.assertEqual(res.status, '302 Found')
            self.assertEqual(res.location, 'http://localhost/trycaptcha/')
            res = self.testapp.get(res.location)
            self.assertEqual(self.signup_userdb.db_count(), 0)
            res = res.form.submit()
            self.assertEqual(self.signup_userdb.db_count(), 0)
