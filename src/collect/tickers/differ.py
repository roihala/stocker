import logging
from collections.abc import Iterable
from copy import deepcopy
from itertools import zip_longest, tee

logger = logging.getLogger('Collect')


class Differ(object):
    def __init__(self):
        self._hierarchy = None
        self._diffs = []

    def get_diffs(self, latest, current, hierarchy=None):
        """
        This function will return the diffs between two deep dictionaries as 'simple changes'.
        which means that whenever a deep change is encountered, differ will follow the hierarchy provided by the user
        to alert the change as long as it follows the hierarchy

        A lot of examples can be found under test_differ.

        :param latest: Latest dict
        :param current: Current dict
        :param hierarchy: A dict of the following schema:
        "key": [layers order]
        e.g:
        {'otcAward': [dict, 'best50'],
        'notes': [list],
        'officers': [list, dict, 'name'],
        'descriptors': [dict, 'name', list]}

        *Note that after a dict layer an index must come

        :return: List of changes, where every change will follow the schema:
        "changed_key": list of keys that have changed,
        "old": old value,
        "new": new value,
        "diff_type": on of: add, remove, change
        """

        self._diffs = []

        if hierarchy:
            self._hierarchy = hierarchy

        for key in set(list(latest.keys()) + list(current.keys())):
            latest_value, current_value = latest.get(key), current.get(key)

            if latest_value != current_value:
                try:
                    # If the key is nested and nested_keys structure was provided
                    # If they are iterables and have the same type
                    if hierarchy is not None and key in hierarchy.keys() and Differ.__is_iterable(current_value):
                        # Initiating empty iterable (list or dict) when getting None
                        if not issubclass(type(latest_value), type(current_value)):
                            latest_value = current_value.__class__()
                        self.__handle_nested_keys([key], latest_value, current_value, iter(self._hierarchy[key]))

                        continue

                except Exception as e:
                    logger.warning(f"Couldn't generate diffs for {key} between current {current} to latest {latest}")
                    logger.exception(e)

                # If couldn't or wouldn't generate nested diff
                diff_type = self.__get_diff_type(current=current_value, latest=latest_value)
                if diff_type:
                    self._diffs.append(Differ.__build_diff(diff_type, key, latest_value, current_value))

        return self._diffs

    def __handle_nested_keys(self, keys, latest, current, layers, dig_mode=False):
        """
        This function will recursively handle nested keys while iterating throughout the layers
        until the iterator stops

        :param keys: A list of keys
        :param layers: layers iterator
        :param dig_mode: Is used to declare that we currently seek to tear down the layers because we found a diff
        :return: None
        """
        if latest == current:
            return

        try:
            self.__next_layer(keys, latest, current, layers, dig_mode)

        except StopIteration:
            # We finished, lets append changes
            if dig_mode:
                self.__dig_mode(is_last_layer=True, keys=keys, latest=latest, current=current)

            else:
                diff_type = self.__get_diff_type(current, latest)
                if diff_type:
                    self._diffs.append(Differ.__build_diff(diff_type, keys, latest, current))

        except (KeyError, TypeError, Exception):
            # Whoops, wrong hierarchy
            self._diffs.append(Differ.__build_diff('change', keys, latest, current))
            raise DifferException('Invalid hierarchy structure for {key} --->\n{structure}'
                                  .format(key=keys, structure=self._hierarchy))

    def __next_layer(self, keys, latest, current, layers, dig_mode=False):
        layer = next(layers)

        if issubclass(layer, dict):
            # After a dict layer a key must come
            key = next(layers)
            if not isinstance(key, str):
                raise DifferException('A key must come after a dict layer')
            keys.append(key)

            if dig_mode:
                self.__dig_mode(layer, keys=deepcopy(keys), latest=latest, current=current, layers=tee(layers)[1])

            elif latest[key] != current[key]:
                self.__handle_nested_keys(deepcopy(keys), latest[key], current[key], tee(layers)[1])

        elif issubclass(layer, list):
            if dig_mode:
                self.__dig_mode(layer, keys=deepcopy(keys), latest=latest, current=current, layers=tee(layers)[1])

            # Filtering identical values
            latest, current = [value for value in latest if value not in current], \
                              [value for value in current if value not in latest]

            # Cloning the iterator to allow digging
            layers_clones = tee(layers, max(len(latest), len(current)) + 1)

            for index, part in enumerate(zip_longest(latest, current)):
                latest_part, current_part = part[0], part[1]

                if current_part is None:
                    self.__handle_nested_keys(deepcopy(keys), latest_part, None, layers_clones[index + 1],
                                              dig_mode=True)
                elif latest_part is None:
                    self.__handle_nested_keys(deepcopy(keys), None, current_part, layers_clones[index + 1],
                                              dig_mode=True)
                else:
                    self.__handle_nested_keys(deepcopy(keys), latest_part, current_part, layers_clones[index + 1])
        else:
            raise DifferException('Differ\'s hierarchy only supports lists, dicts, and dict_keys right now')

    @staticmethod
    def __get_diff_type(current, latest):
        no_current, no_latest = str(current) in ['None', 'nan', ''], str(latest) in ['None', 'nan', '']

        if (no_current and no_latest) or (current == latest):
            return None
        elif no_current:
            return 'remove'
        elif no_latest:
            return 'add'
        else:
            return 'change'

    def __dig_mode(self, layer=None, is_last_layer=False, **kwargs):
        diff_type = self.__get_diff_type(current=kwargs['current'], latest=kwargs['latest'])

        if diff_type in [None, 'change']:
            raise DifferException('Dig mode must supports only add/remove')

        current_or_latest = 'latest' if diff_type == 'remove' else 'current'

        if is_last_layer:
            self._diffs.append(Differ.__build_diff(diff_type, **kwargs))

        elif issubclass(layer, dict):
            kwargs[current_or_latest] = kwargs[current_or_latest][kwargs['keys'][-1]]
            self.__handle_nested_keys(**kwargs, dig_mode=True)

        elif issubclass(layer, list):
            for part in kwargs[current_or_latest]:
                kwargs[current_or_latest] = part
                self.__handle_nested_keys(**kwargs, dig_mode=True)

        else:
            raise DifferException("Can't figure out which dig mode type to use")

    @staticmethod
    def __is_iterable(value):
        """
        Returning whether value is iterable, strings are not included because they don't add a dimension to the dict
        """
        if isinstance(value, Iterable) and not isinstance(value, str):
            return True
        return False

    @staticmethod
    def __build_diff(diff_type, keys, latest, current):
        return {
            "changed_key": keys,
            "old": latest,
            "new": current,
            "diff_type": diff_type
        }


class DifferException(Exception):
    pass
