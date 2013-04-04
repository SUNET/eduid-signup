import os
import re

from pyramid.config import Configurator

from eduid_signup.i18n import locale_negotiator

def read_setting_from_env(settings, key, default=None):
    env_variable = key.upper()
    if env_variable in os.environ:
        return os.environ[env_variable]
    else:
        return settings.get(key, default)


def includeme(config):
    config.add_route('home', '/')


def main(global_config, **settings):

    available_languages = read_setting_from_env(settings, 'available_languages', 'en es')
    settings['available_languages'] = [
        lang for lang in available_languages.split(' ') if lang
        ]

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
