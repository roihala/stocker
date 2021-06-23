import inspect


class Actions(object):
    # Actions
    FREE_TRIAL = 'free_trial'
    TOOLS = 'tools'
    BACK_TO_MENU = 'back_to_menu'
    INFO = 'info'
    ALERTS = 'alerts'
    DILUTION = 'dilution'
    ACTIVATE = 'activate'
    AGREE = 'agree'

    class SurveyActions(object):
        START_SURVEY = 'start_survey'
        SKIP = 'Skip'
        CONTINUE = 'continue'
        BACK = '« Back'
        SKIP_SURVEY = 'skip_survey'
        LOWER_THAN_5 = 'lower_than_5'
        LOWER_THAN_2 = 'lower_than_2'
        LOWER_THAN_1 = 'lower_than_1'
        LOWER_THAN_CURRENT = 'lower_than_current'
        LOWER_THAN_QB = 'lower_than_qb'
        ADD_TO_WATCHLIST = 'add_to_watchlist'
        REPLACE_WATCHLIST = 'replace_watchlist'
        REMOVE_FROM_WATHCLIST = 'remove_from_watchlist'

        @classmethod
        def get_survey_actions(cls, exclude_wathclist=False):
            all_actions = [member[1] for member in inspect.getmembers(cls, lambda a: not (inspect.isroutine(a))) if not member[0].startswith('_')]
            return all_actions if not exclude_wathclist else [action for action in all_actions if action not in cls.get_watchlist_actions()]

        @classmethod
        def get_price_actions(cls):
            return [cls.LOWER_THAN_1, cls.LOWER_THAN_2, cls.LOWER_THAN_5]

        @classmethod
        def get_tier_actions(cls):
            return [cls.LOWER_THAN_CURRENT, cls.LOWER_THAN_QB]

        @classmethod
        def get_watchlist_actions(cls):
            return [cls.ADD_TO_WATCHLIST, cls.REPLACE_WATCHLIST, cls.REMOVE_FROM_WATHCLIST]
