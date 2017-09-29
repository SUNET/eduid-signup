from pyramid.i18n import TranslationStringFactory, get_localizer

import logging
logger = logging.getLogger(__name__)

translation_domain = 'eduid_signup'
TranslationString = TranslationStringFactory(translation_domain)


def locale_negotiator(request):
    settings = request.registry.settings
    available_languages = settings['available_languages'].keys()
    cookie_name = settings['lang_cookie_name']

    logger.debug("locale_negotiator, available_languages: {}".format(available_languages))
    logger.debug("locale_negotiator, cookie_name: {}".format(cookie_name))

    cookie_lang = request.cookies.get(cookie_name, None)

    logger.debug("locale_negotiator, cookie_lang: {}".format(cookie_lang))

    if cookie_lang and cookie_lang in available_languages:
        logger.debug("locale_negotiator, returning cookie_lang: {}".format(cookie_lang))
        return cookie_lang

    locale_name = request.accept_language.best_match(available_languages)

    if locale_name not in available_languages:
        locale_name = settings.get('default_locale_name', 'sv')

    logger.debug("locale_negotiator, locale_name: {}".format(locale_name))

    return locale_name


def add_localizer(event):
    request = event.request
    localizer = get_localizer(request)

    def auto_translate(string):
        return localizer.translate(TranslationString(string))

    request.localizer = localizer
    request.translate = auto_translate
