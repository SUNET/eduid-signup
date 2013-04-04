import re

from pyramid.config import Configurator


def includeme(config):
    config.add_route('home', '/')


def main(global_config, **settings):
    config = Configurator(settings=settings)

    config.include('pyramid_jinja2')

    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
