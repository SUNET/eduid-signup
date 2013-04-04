import re

from pyramid.config import Configurator


def includeme(config):
    config.add_route('home', '/')


def main(global_config, **settings):
    config = Configurator(settings=settings)

    # include other packages
    config.include('pyramid_jinja2')

    # global directives
    config.add_static_view('static', 'static', cache_max_age=3600)

    # eudid specific configuration
    includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return config.make_wsgi_app()
