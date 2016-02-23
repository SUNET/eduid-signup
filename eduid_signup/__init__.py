import re

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPNotFound
from pyramid.i18n import get_locale_name

from eduid_am.celery import celery
#from eduid_am.userdb import UserDB
from eduid_common.config.parsers import IniConfigParser
from eduid_signup.i18n import locale_negotiator
from eduid_userdb import MongoDB, UserDB
from eduid_userdb.signup import SignupUserDB


def includeme(config):
    # DB setup
    _mongodb_tou = MongoDB(config.registry.settings['mongo_uri'], 'eduid_tou')
    _userdb = UserDB(config.registry.settings['mongo_uri'], 'eduid_am')
    _signup_db = SignupUserDB(config.registry.settings['mongo_uri'], 'eduid_signup')

    # Create mongodb client instance and store it in our config,
    # and make a getter lambda for pyramid to retreive it
    config.registry.settings['signup_db'] = _signup_db
    config.add_request_method(lambda x: x.registry.settings['signup_db'], 'signup_db', reify=True)

    # Create userdb instance and store it in our config,
    # and make a getter lambda for pyramid to retreive it (will be available as 'request.userdb')
    config.registry.settings['userdb'] = _userdb
    config.add_request_method(lambda x: x.registry.settings['userdb'], 'userdb', reify=True)

    # store mongodb tou client instance in our config,
    # and make a getter lambda for pyramid to retreive it
    config.registry.settings['mongodb_tou'] = _mongodb_tou
    config.add_request_method(lambda x: x.registry.settings['mongodb_tou'].get_database(), 'toudb', reify=True)

    # root views
    config.add_route('home', '/')
    config.add_route('help', '/help/')
    config.add_route('success', '/success/')
    config.add_route('email_verification_link', '/email_verification/{code}/')
    config.add_route('sna_account_created', '/sna_account_created/')
    config.add_route('trycaptcha', '/trycaptcha/')
    config.add_route('resend_email_verification', '/resend_email_verification/')
    config.add_route('email_already_registered', '/email_already_registered/')
    config.add_route('verification_code_form', '/verification_code_form/')
    config.add_route('review_fetched_info', '/review_fetched_info/')
    config.add_route('set_language', '/set_language/')

    config.add_route('error500test', '/error500test/')
    config.add_route('error500', '/error500/')

    config.add_route('error404', '/error404/')

    config.set_request_property(get_locale_name, 'locale', reify=True)
    config.add_subscriber('eduid_signup.i18n.add_localizer',
                          'pyramid.events.NewRequest')

    if not config.registry.settings.get('testing', False):
        config.add_view(context=Exception,
                        view='eduid_signup.views.exception_view',
                        renderer='templates/error500.jinja2')
        config.add_view(context=HTTPNotFound,
                        view='eduid_signup.views.exception_view',
                        renderer='templates/error404.jinja2')

    # Favicon
    config.add_route('favicon', '/favicon.ico')
    config.add_view('eduid_signup.views.favicon_view', route_name='favicon')


def main(global_config, **settings):
    settings = dict(settings)

    cp = IniConfigParser('')  # Init without config file as it is already loaded

    # read pyramid_mailer options
    for key, default in (
        ('host', 'localhost'),
        ('port', '25'),
        ('username', None),
        ('password', None),
        ('default_sender', 'no-reply@example.com')
    ):
        option = 'mail.' + key
        settings[option] = cp.read_setting_from_env(settings, option, default)

    # Parse settings before creating the configurator object
    available_languages = cp.read_mapping(settings,
                                          'available_languages',
                                          default={'en': 'English',
                                                   'sv': 'Svenska'})

    settings['available_languages'] = available_languages

    for item in (
        'mongo_uri',
        'profile_link',
        'dashboard_link',
        'site.name',
        'signup_hostname',
        'signup_baseurl',
        'reset_password_link',
        'vccs_url',
        'auth_shared_secret',
        'student_link',
        'technicians_link',
        'staff_link',
        'faq_link',
        'privacy_link',
    ):
        settings[item] = cp.read_setting_from_env(settings, item, None)
        if settings[item] is None:
            raise ConfigurationError('The {0} configuration option is required'.format(item))

    # reCaptcha
    settings['recaptcha_public_key'] = cp.read_setting_from_env(settings,
                                                                'recaptcha_public_key',
                                                                None)

    settings['recaptcha_private_key'] = cp.read_setting_from_env(settings,
                                                                 'recaptcha_private_key',
                                                                 None)
    settings['lang_cookie_domain'] = cp.read_setting_from_env(settings,
                                                              'lang_cookie_domain',
                                                              None)

    settings['lang_cookie_name'] = cp.read_setting_from_env(settings,
                                                            'lang_cookie_name',
                                                            'lang')

    mongo_replicaset = cp.read_setting_from_env(settings, 'mongo_replicaset', None)
    if mongo_replicaset is not None:
        settings['mongo_replicaset'] = mongo_replicaset

    # configure Celery broker
    broker_url = cp.read_setting_from_env(settings, 'broker_url', 'amqp://')
    celery_result_backend = cp.read_setting_from_env(settings, 'broker_url', '')
    celery.conf.update({
        'MONGO_URI': settings.get('mongo_uri'),
        'BROKER_URL': broker_url,
        'CELERY_RESULT_BACKEND': celery_result_backend,
        'CELERY_TASK_SERIALIZER': 'json',
        # Avoid broken connections across firewall by disabling pool
        # http://docs.celeryproject.org/en/latest/configuration.html#broker-pool-limit
        'BROKER_POOL_LIMIT': 0,
    })
    settings['celery'] = celery
    settings['broker_url'] = broker_url
    settings['celery_result_backend'] = celery_result_backend

    settings['google_callback'] = 'eduid_signup.sna_callbacks.google_callback'
    settings['facebook_callback'] = 'eduid_signup.sna_callbacks.facebook_callback'
    settings['liveconnect_callback'] = 'eduid_signup.sna_callbacks.liveconnect_callback'

    settings['password_length'] = int(cp.read_setting_from_env(settings, 'password_length', '10'))

    settings['account_creation_timeout'] = int(cp.read_setting_from_env(settings,
                                                                        'account_creation_timeout',
                                                                        '10'))

    # The configurator is the main object about configuration
    config = Configurator(settings=settings, locale_negotiator=locale_negotiator)

    try:
        settings['session.cookie_expires'] = int(settings['session.cookie_expires'])
    except ValueError:
        raise ConfigurationError('session.cookie_expires must be a integer value')

    # include other packages
    config.include('pyramid_beaker')
    config.include('pyramid_jinja2')

    if 'testing' in settings and asbool(settings['testing']):
        config.include('pyramid_mailer.testing')
    elif 'development' in settings and asbool(settings['development']):
        config.include('pyramid_mailer.testing')
    else:
        config.include('pyramid_mailer')

    config.include('pyramid_tm')
    config.include('pyramid_sna')

    # global directives
    if settings.get('static_url', False):
        config.add_static_view(settings['static_url'], 'static')
    else:
        config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_translation_dirs('eduid_signup:locale/')

    # eduid specific configuration
    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
