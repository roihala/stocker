import logging


def disable_apscheduler_logs():
    logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
