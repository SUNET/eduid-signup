import os
import re

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool
from pyramid.httpexceptions import HTTPNotFound
from pyramid.i18n import get_locale_name

from eduid_am.celery import celery
from eduid_signup.db import MongoDB, get_db
from eduid_signup.i18n import locale_negotiator
from eduid_signup.userdb import UserDB, get_userdb


def read_setting_from_env(settings, key, default=None):
    env_variable = key.upper()
    if env_variable in os.environ:
        return os.environ[env_variable]
    else:
        return settings.get(key, default)


def includeme(config):
    # DB setup
    mongo_replicaset = config.registry.settings.get('mongo_replicaset', None)
    if mongo_replicaset is not None:
        mongodb = MongoDB(config.registry.settings['mongo_uri'],
                          replicaSet=mongo_replicaset)
    else:
        mongodb = MongoDB(config.registry.settings['mongo_uri'])
    config.registry.settings['mongodb'] = mongodb
    config.registry.settings['db_conn'] = mongodb.get_connection

    config.set_request_property(get_db, 'db', reify=True)

    userdb = UserDB(config.registry.settings)
    config.registry.settings['userdb'] = userdb
    config.add_request_method(get_userdb, 'userdb', reify=True)

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


def main(global_config, **settings):

    # read pyramid_mailer options
    for key, default in (
        ('host', 'localhost'),
        ('port', '25'),
        ('username', None),
        ('password', None),
        ('default_sender', 'no-reply@example.com')
    ):
        option = 'mail.' + key
        settings[option] = read_setting_from_env(settings, option, default)

    # Parse settings before creating the configurator object
    available_languages = read_setting_from_env(settings, 'available_languages', 'en es')
    settings['available_languages'] = [
        lang for lang in available_languages.split(' ') if lang
    ]

    for item in (
        'mongo_uri',
        'mongo_uri_am',
        'profile_link',
        'site.name',
        'reset_password_link',
        'vccs_url',
        'auth_shared_secret',
    ):
        settings[item] = read_setting_from_env(settings, item, None)
        if settings[item] is None:
            raise ConfigurationError('The {0} configuration option is required'.format(item))

    # reCaptcha
    settings['recaptcha_public_key'] = read_setting_from_env(settings,
                                                             'recaptcha_public_key',
                                                             None)

    settings['recaptcha_private_key'] = read_setting_from_env(settings,
                                                              'recaptcha_private_key',
                                                              None)
    settings['lang_cookie_domain'] = read_setting_from_env(settings,
                                                           'lang_cookie_domain',
                                                           None)

    settings['lang_cookie_name'] = read_setting_from_env(settings,
                                                         'lang_cookie_name',
                                                         'lang')

    mongo_replicaset = read_setting_from_env(settings, 'mongo_replicaset', None)
    if mongo_replicaset is not None:
        settings['mongo_replicaset'] = mongo_replicaset

    # configure Celery broker
    broker_url = read_setting_from_env(settings, 'broker_url', 'amqp://')
    celery.conf.update(BROKER_URL=broker_url)
    settings['celery'] = celery
    settings['broker_url'] = broker_url

    settings['google_callback'] = 'eduid_signup.sna_callbacks.google_callback'
    settings['facebook_callback'] = 'eduid_signup.sna_callbacks.facebook_callback'
    settings['liveconnect_callback'] = 'eduid_signup.sna_callbacks.liveconnect_callback'

    settings['password_length'] = int(read_setting_from_env(settings, 'password_length', '10'))

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
    else:
        config.include('pyramid_mailer')

    config.include('pyramid_tm')
    config.include('pyramid_sna')

    # global directives
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_translation_dirs('eduid_signup:locale/')

    # eudid specific configuration
    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
