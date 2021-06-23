import arrow


class BaseBot(object):
    def __init__(self, mongo_db, bot_instance, logger, debug):
        self.mongo_db = mongo_db
        self.bot_instance = bot_instance
        self.logger = logger
        self.debug = debug

    def _generate_log_json(self, user, action, is_success, description=None, payload=None):
        log = {
            'action': action,
            'date': arrow.utcnow().format(),
            'success': is_success,
            'chat_id': user.id,
            'user_name': user.name
        }
        log.update({'payload': payload}) if payload else None
        log.update({'appendix': description}) if payload else None
        return log

    def _is_high_permission_user(self, user_name, chat_id):
        return bool(
            self.mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id, 'permissions': 'high'}))
