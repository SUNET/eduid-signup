import re
from copy import deepcopy

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPNotFound
from pyramid.i18n import get_locale_name

from eduid_am.celery import celery
from eduid_common.config.parsers import IniConfigParser
from eduid_signup.i18n import locale_negotiator
from eduid_signup.config import SignupConfig
from eduid_userdb import MongoDB, UserDB
from eduid_userdb.signup import SignupUserDB

import logging
logger = logging.getLogger(__name__)


def includeme(configurator, config):
    # DB setup
    _mongodb_tou = MongoDB(config.mongo_uri, 'eduid_tou')
    _userdb = UserDB(config.mongo_uri, 'eduid_am')
    _signup_db = SignupUserDB(config.mongo_uri, 'eduid_signup')

    # Create mongodb client instance and store it in our configurator,
    # and make a getter lambda for pyramid to retreive it
    configurator.registry.settings['signup_db'] = _signup_db
    configurator.add_request_method(lambda x: x.registry.settings['signup_db'], 'signup_db', reify=True)

    # Create userdb instance and store it in our configurator,
    # and make a getter lambda for pyramid to retreive it (will be available as 'request.userdb')
    configurator.registry.settings['userdb'] = _userdb
    configurator.add_request_method(lambda x: x.registry.settings['userdb'], 'userdb', reify=True)

    # store mongodb tou client instance in our configurator,
    # and make a getter lambda for pyramid to retreive it
    configurator.registry.settings['mongodb_tou'] = _mongodb_tou
    configurator.add_request_method(lambda x: x.registry.settings['mongodb_tou'].get_database(), 'toudb', reify=True)

    # store SignupConfig instance in our configurator,
    # and make a getter lambda for pyramid to retreive it
    # By calling it exactly 'signupconfig', Pycharm provides code completion using the class SignupConfig.
    configurator.registry.settings['signupconfig'] = config
    configurator.add_request_method(lambda x: x.registry.settings['signupconfig'], 'signupconfig', reify=True)

    # root views
    configurator.add_route('home', '/')
    configurator.add_route('help', '/help/')
    configurator.add_route('success', '/success/')
    configurator.add_route('email_verification_link', '/email_verification/{code}/')
    configurator.add_route('sna_account_created', '/sna_account_created/')
    configurator.add_route('trycaptcha', '/trycaptcha/')
    configurator.add_route('resend_email_verification', '/resend_email_verification/')
    configurator.add_route('email_already_registered', '/email_already_registered/')
    configurator.add_route('verification_code_form', '/verification_code_form/')
    configurator.add_route('review_fetched_info', '/review_fetched_info/')
    configurator.add_route('set_language', '/set_language/')

    configurator.add_route('error500test', '/error500test/')
    configurator.add_route('error500', '/error500/')

    configurator.add_route('error404', '/error404/')

    configurator.set_request_property(get_locale_name, 'locale', reify=True)
    configurator.add_subscriber('eduid_signup.i18n.add_localizer',
                                'pyramid.events.NewRequest')

    if not config.testing:
        configurator.add_view(context=Exception,
                              view='eduid_signup.views.exception_view',
                              renderer='templates/error500.jinja2')
        configurator.add_view(context=HTTPNotFound,
                              view='eduid_signup.views.exception_view',
                              renderer='templates/error404.jinja2')

    # Favicon
    configurator.add_route('favicon', '/favicon.ico')
    configurator.add_view('eduid_signup.views.favicon_view', route_name= 'favicon')


def init_settings_from_dict(settings_in):
    """
    Make Pyramid App Settings from the input given to the Pyramid app on startup.

    The result is meant to be passed to a Pyramid Configurator as `settings'.

    :param settings_in: Configuration data
    :return: App settings, and configuration
    :rtype: dict, SignupConfig
    """
    _settings = dict(deepcopy(settings_in))  # don't mess with callers data
    pyramid_settings = {}
    rename = {'session.cookie_expires': 'session_cookie_expires',
              'site.name': 'site_name',
              }
    for x in _settings.keys():
        if x.startswith('jinja2.'):
            # Jinja2 settings should go into the Pyramid settings dict
            pyramid_settings[x] = _settings[x]
            del _settings[x]
        if x in rename:
            logger.debug('Renaming option {!s} -> {!s}'.format(x, rename[x]))
            _settings[rename[x]] = _settings[x]
            del _settings[x]

    cp = IniConfigParser('')  # Init without config file as it is already loaded

    signup_config = SignupConfig(cp, _settings)

    for name in signup_config.keys():
        # Copy SNA related options to pyramid_settings where the pyramid_sna module
        # expects to find them
        if name.startswith('google_') or name.startswith('facebook_') or \
                name.startswith('liveconnect_'):
            pyramid_settings[name] = getattr(signup_config, name)

    pyramid_settings['session.key'] = signup_config.session_cookie_name

    return pyramid_settings, signup_config


def main(global_config, **settings_in):

    settings, config = init_settings_from_dict(dict(settings_in))

    # configure Celery broker
    celery.conf.update({
        'MONGO_URI': config.mongo_uri,
        'BROKER_URL': config.broker_url,
        'CELERY_RESULT_BACKEND': config.celery_result_backend,
        'CELERY_TASK_SERIALIZER': 'json',
        # Avoid broken connections across firewall by disabling pool
        # http://docs.celeryproject.org/en/latest/configuration.html#broker-pool-limit
        'BROKER_POOL_LIMIT': 0,
    })
    #settings.celery = celery

    # The configurator is the main object about configuration
    configurator = Configurator(settings=settings, locale_negotiator=locale_negotiator)

    # include other packages
    configurator.include('pyramid_beaker')
    configurator.include('pyramid_jinja2')

    if config.testing or config.development:
        configurator.include('pyramid_mailer.testing')
    else:
        configurator.include('pyramid_mailer')

    configurator.include('pyramid_tm')
    configurator.include('pyramid_sna')

    # global directives
    if config.static_url:
        configurator.add_static_view(config.static_url, 'static')
    else:
        configurator.add_static_view('static', 'static', cache_max_age=3600)

    configurator.add_translation_dirs('eduid_signup:locale/')

    # eduid specific configuration
    includeme(configurator, config)

    configurator.scan(ignore=[re.compile('.*tests.*').search, '.testing'])
    return configurator.make_wsgi_app()
