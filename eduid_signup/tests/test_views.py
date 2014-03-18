from pyramid_sna.compat import urlparse
from eduid_signup.testing import FunctionalTests
from mock import patch


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
        self.assertEqual(res.location, 'http://localhost/success/')


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


class GoogleCallbackTests(FunctionalTests):

    def test_callback(self):
        # call the login to fill the session
        res = self.testapp.get('/google/login', {
            'next_url': 'https://localhost/foo/bar',
        })
        self.assertEqual(res.status, '302 Found')
        url = urlparse.urlparse(res.location)
        query = urlparse.parse_qs(url.query)
        state = query['state'][0]

        with patch('requests.post') as fake_post:
            # taken from pyramid_sna
            fake_post.return_value.status_code = 200
            fake_post.return_value.json = lambda: {
                'access_token': '1234',
            }
            with patch('requests.get') as fake_get:
                fake_get.return_value.status_code = 200
                fake_get.return_value.json = lambda: {
                    'id': '789',
                    'name': 'John Smith',
                    'given_name': 'John',
                    'family_name': 'Smith',
                    'email': 'johnsmith@example.com',
                }

                res = self.testapp.get('/google/callback', {
                    'code': '1234',
                    'state': state,
                })
        res = self.testapp.get('/review_fetched_info/')
        self.assertEqual(self.db.registered.find({}).count(), 0)
        res = res.form.submit('action')
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(self.db.registered.find({}).count(), 1)
