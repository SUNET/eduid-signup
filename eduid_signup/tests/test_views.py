from eduid_signup.testing import FunctionalTests


class HomeViewTests(FunctionalTests):

    def test_home(self):
        res = self.testapp.get('/')
        self.assertEqual(res.status, '200 OK')
        res.mustcontain(
            'Welcome to eduID!',
            'Create an account that will allow you access to all Swedish Universities.',
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
        
    def test_help_in_spanish(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'es',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Ayuda')

    def test_help_in_unknown_language(self):
        res = self.testapp.get('/help/', headers={
            'Accept-Language': 'xx',
        })
        self.assertEqual(res.status, '200 OK')
        res.mustcontain('Help')
