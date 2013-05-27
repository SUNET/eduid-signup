import os
import re

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool

from eduid_am.celery import celery
from eduid_signup.db import MongoDB, get_db
from eduid_signup.i18n import locale_negotiator


def read_setting_from_env(settings, key, default=None):
    env_variable = key.upper()
    if env_variable in os.environ:
        return os.environ[env_variable]
    else:
        return settings.get(key, default)


def includeme(config):
    # DB setup
    mongodb = MongoDB(config.registry.settings['mongo_uri'])
    config.registry.settings['mongodb'] = mongodb
    config.registry.settings['db_conn'] = mongodb.get_connection

    config.set_request_property(get_db, 'db', reify=True)

    # root views
    config.add_route('home', '/')
    config.add_route('help', '/help/')
    config.add_route('success', '/success/')
    config.add_route('email_verification_link', '/email_verification/{code}/')
    config.add_route('trycaptcha', '/trycaptcha/')
    config.add_route('resend_email_verification', '/resend_email_verification')
    config.add_route('email_already_registered', '/email_already_registered/')


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
        'profile_link',
        'site.name',
        'reset_password_link'
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

    # configure Celery broker
    broker_url = read_setting_from_env(settings, 'broker_url', 'amqp://')
    celery.conf.update(BROKER_URL=broker_url)
    settings['celery'] = celery
    settings['broker_url'] = broker_url

    settings['google_callback'] = 'eduid_signup.sna_callbacks.google_callback'
    settings['facebook_callback'] = 'eduid_signup.sna_callbacks.facebook_callback'

    # The configurator is the main object about configuration
    config = Configurator(settings=settings, locale_negotiator=locale_negotiator)

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
