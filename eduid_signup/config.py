from pyramid.settings import asbool

import logging
logger = logging.getLogger(__name__)

__author__ = 'ft'


class EduIDConfig(object):

    def __init__(self, parser, settings):
        self._parser = parser
        self._settings = settings
        self._cache = {}

        # Check that all required settings are present
        failed = []
        for name in self.keys():
            try:
                foo = getattr(self, name)
            except ValueError as exc:
                logger.error('{!s}'.format(exc))
                failed.append(name)
            if failed:
                raise ValueError('The following configuration options failed to load: {!s}'.format(failed))

    def keys(self):
        """
        Return iterator for all configuration option names.

        :return: All configuration options supported.
        :rtype: iterator
        """
        for name in dir(self):
            if name.startswith('_'):
                continue
            yield(name)

    def _fetch_required(self, name, type_= 'unicode'):
        """
        Fetch a required configuration parameters value, or raise a ValueError exception
        if it is not found in the configuration backend.

        Return cached data if available, otherwise call _fetch_from_backend.

        :param name: Parameter to fetch
        :param type_: Convert result to this data type
        :return: Configuration value
        """
        if name not in self._settings:
            raise ValueError('Required setting {!r} not set'.format(name))
        return self._fetch(name, None, type_ = type_)

    def _fetch(self, name, default, type_= 'unicode'):
        """
        Fetch a configuration parameters value.

        Return cached data if available, otherwise call _fetch_from_backend.

        :param name: Parameter to fetch
        :param default: Default value
        :param type_: Convert result to this data type
        :return: Configuration value
        """
        if name not in self._cache:
            self._cache[name] = self._fetch_from_backend(name, default, type_ = type_)
        return self._cache[name]

    def _fetch_from_backend(self, name, default, type_= 'unicode'):
        """

        :param name:
        :param default:
        :param type_:
        :return:
        """
        if name in self._settings:
            if type_ == 'mapping':
                value = self._parser.read_mapping(self._settings, name, default)
            else:
                value = self._parser.read_setting_from_env(self._settings, name, default)
            return self._type_cast(name, value, type_)
        return default

    def _type_cast(self, name, value, type_):
        try:
            return self._type_cast_safe(value, type_)
        except Exception as exc:
            raise ValueError('Failed parsing configuration option {!r}: {!s}'.format(name, exc))

    def _type_cast_safe(self, value, type_):
        if type_ is 'unicode':
            return unicode(value)
        if type_ == 'int':
            return int(value)
        if type_ == 'bool':
            return asbool(value)
        raise ValueError('Type casting to {!r} not implemented'.format(type_))


class SignupConfig(EduIDConfig):

    def __init__(self, parser, settings):
        super(SignupConfig, self).__init__(parser, settings)

        for x in settings.keys():
            if not hasattr(self, x):
                logger.warning('Unknown configuration option: {!s}'.format(x))

    @property
    def account_creation_timeout(self):
        """
        :return: something
        :rtype: int
        """
        return self._fetch('account_creation_timeout', 3, type_= 'int')

    @property
    def auth_shared_secret(self):
        """
        :return: Authentication key shared with eduid Dashboard, for letting newly signed
                 users log in to the dashboard without visiting the IdP.
        :rtype: unicode
        """
        return self._fetch_required('auth_shared_secret')

    @property
    def available_languages(self):
        """
        :return: something
        :rtype: mapping
        """
        return self._fetch('available_languages', {'en': 'English', 'sv': 'Svenska'}, type_= 'mapping')

    @property
    def broker_url(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('broker_url', 'amqp://')

    @property
    def celery_result_backend(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('celery_result_backend', 'amqp')

    @property
    def dashboard_link(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('dashboard_link')

    @property
    def default_finish_url(self):
        """
        :return: Default URL to send user to after successful signup.
                 If not provided, a URL from the Pyramid Context is used instead
                 (which I think means it is passed in from the page directing
                 the user to the Signup application).
        :rtype: unicode
        """
        return self._fetch_required('profile_link')

    @property
    def default_locale_name(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('default_locale_name', 'en')

    @property
    def development(self):
        """
        :return: something
        :rtype: bool
        """
        return self._fetch('development', False, type_= 'bool')

    @property
    def email_credentials(self):
        """
        :return: If true, send users credentials to the email address used on completed signup.
        :rtype: bool
        """
        return self._fetch('email_credentials', False, type_= 'bool')

    @property
    def facebook_app_id(self):
        """
        :return: Social signup using Facebook. See pyramid-sna module.
        :rtype: bool
        """
        return self._fetch('facebook_app_id', '')

    @property
    def facebook_app_secret(self):
        """
        :return: Social signup using Facebook. See pyramid-sna module.
        :rtype: bool
        """
        return self._fetch('facebook_app_secret', '')

    @property
    def facebook_auth_enabled(self):
        """
        :return: Enable social signup using Facebook
        :rtype: bool
        """
        return self._fetch('facebook_auth_enabled', False, type_= 'bool')

    @property
    def facebook_callback(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('facebook_callback', 'eduid_signup.sna_callbacks.facebook_callback')

    @property
    def faq_link(self):
        """
        :return: URL for the top nagigation bar in base.jinja2
        :rtype: unicode
        """
        return self._fetch_required('faq_link')

    @property
    def google_auth_enabled(self):
        """
        :return: Enable social signup using Google
        :rtype: bool
        """
        return self._fetch('google_auth_enabled', False, type_= 'bool')

    @property
    def google_callback(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('google_callback', 'eduid_signup.sna_callbacks.google_callback')

    @property
    def google_client_id(self):
        """
        :return: Social signup using Facebook. See pyramid-sna module.
        :rtype: bool
        """
        return self._fetch('google_client_id', '')

    @property
    def google_client_secret(self):
        """
        :return: Social signup using Google. See pyramid-sna module.
        :rtype: bool
        """
        return self._fetch('google_client_secret', '')

    @property
    def host(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('host', 'localhost')

    @property
    def lang_cookie_domain(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('lang_cookie_domain')

    @property
    def lang_cookie_name(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('lang_cookie_name', 'lang')

    @property
    def liveconnect_auth_enabled(self):
        """
        :return: Enable social signup using Microsoft Live
        :rtype: bool
        """
        return self._fetch('liveconnect_auth_enabled', False, type_= 'bool')

    @property
    def liveconnect_callback(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('liveconnect_callback', 'eduid_signup.sna_callbacks.liveconnect_callback')

    @property
    def mail_default_sender(self):
        """
        :return: Sender address for verification emails.
        :rtype: unicode
        """
        return self._fetch('mail_default_sender', 'no-reply@example.com')

    @property
    def mongo_uri(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('mongo_uri')

    @property
    def password(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('password', None)

    @property
    def password_length(self):
        """
        :return: something
        :rtype: int
        """
        return self._fetch('password_length', 10, type_= 'int')

    @property
    def port(self):
        """
        :return: something
        :rtype: int
        """
        return self._fetch('port', 25, type_= 'int')

    @property
    def privacy_link(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('privacy_link')

    @property
    def profile_link(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('profile_link')

    @property
    def recaptcha_private_key(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('recaptcha_private_key', '')

    @property
    def recaptcha_public_key(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('recaptcha_public_key', '')

    @property
    def reset_password_link(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('reset_password_link')

    @property
    def session_cookie_expires(self):
        """
        :return: The expiration time (in seconds?) for the session cookie
        :rtype: int
        """
        return self._fetch_required('session_cookie_expires', type_= 'int')

    @property
    def session_cookie_httponly(self):
        """
        :return: something
        :rtype: bool
        """
        return self._fetch('session_cookie_httponly', True, type_= 'bool')

    @property
    def session_cookie_name(self):
        """
        :return: The name of the session cookie (Pyramid setting 'session.key').
        :rtype: bool
        """
        return self._fetch('session_cookie_name', 'session')


    @property
    def session_cookie_secure(self):
        """
        :return: If true, put the 'secure' HTTP tag on the session cookie
        :rtype: bool
        """
        return self._fetch('session_cookie_secure', True, type_= 'bool')

    @property
    def signup_baseurl(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('signup_baseurl')

    @property
    def signup_hostname(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('signup_hostname')

    @property
    def site_name(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('site_name')

    @property
    def staff_link(self):
        """
        :return: URL for the top nagigation bar in base.jinja2
        :rtype: unicode
        """
        return self._fetch_required('staff_link')

    @property
    def static_url(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('static_url', None)

    @property
    def student_link(self):
        """
        :return: URL for the top nagigation bar in base.jinja2
        :rtype: unicode
        """
        return self._fetch_required('student_link')

    @property
    def technicians_link(self):
        """
        :return: URL for the top nagigation bar in base.jinja2
        :rtype: unicode
        """
        return self._fetch_required('technicians_link')

    @property
    def testing(self):
        """
        :return: something
        :rtype: bool
        """
        return self._fetch('testing', False, type_= 'bool')

    @property
    def tou_version(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('tou_version')

    @property
    def username(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch('username', None)

    @property
    def vccs_url(self):
        """
        :return: something
        :rtype: unicode
        """
        return self._fetch_required('vccs_url')


def pyramid_unpack_config(request):
    """
    Unpack eduid application configuration from a request.

    :param request: Pyramid request
    :return: eduID application configuration
    :rtype: SignupConfig
    """
    cfg = request.signupconfig
    assert isinstance(cfg, SignupConfig)
    return cfg
