import os
import re

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError

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


def main(global_config, **settings):

    # Parse settings before creating the configurator object
    available_languages = read_setting_from_env(settings, 'available_languages', 'en es')
    settings['available_languages'] = [
        lang for lang in available_languages.split(' ') if lang
        ]

    settings['mongo_uri'] = read_setting_from_env(settings, 'mongo_uri', None)
    if settings['mongo_uri'] is None:
        raise ConfigurationError('The mongo_uri configuration option is required')

    # The configurator is the main object about configuration
    config = Configurator(settings=settings, locale_negotiator=locale_negotiator)

    # include other packages
    config.include('pyramid_jinja2')

    # global directives
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_translation_dirs('eduid_signup:locale/')

    # eudid specific configuration
    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
