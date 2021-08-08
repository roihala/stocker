import logging


class BaseFactory(object):
    @staticmethod
    def _instantiate(obj, args, kwargs):
        try:
            return obj(*args, **kwargs)

        except Exception as e:
            logging.getLogger('collector').exception('Could not create an instance of {obj}. exception: {e}'
                                                     .format(obj=obj, e=e))
