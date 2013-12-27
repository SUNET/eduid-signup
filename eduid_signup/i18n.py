from pyramid.i18n import TranslationStringFactory, get_localizer

translation_domain = 'eduid_signup'
TranslationString = TranslationStringFactory(translation_domain)


def locale_negotiator(request):
    settings = request.registry.settings
    available_languages = settings['available_languages']
    cookie_name = settings['lang_cookie_name']

    cookie_lang = request.cookies.get(cookie_name, None)
    if cookie_lang and cookie_lang in available_languages:
        return cookie_lang

    return request.accept_language.best_match(available_languages)


def add_localizer(event):
    request = event.request
    localizer = get_localizer(request)

    def auto_translate(string):
        return localizer.translate(TranslationString(string))

    request.localizer = localizer
    request.translate = auto_translate
