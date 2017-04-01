import abc
from collections import OrderedDict
from copy import copy

import six

from ocgis.base import AbstractOcgisObject


@six.add_metaclass(abc.ABCMeta)
class AbstractCollection(AbstractOcgisObject):
    def __init__(self):
        self._storage = OrderedDict()
        self._storage_id = []

    @property
    def _storage_id_next(self):
        try:
            ret = max(self._storage_id) + 1
        # max of an empty list
        except ValueError:
            if len(self._storage_id) == 0:
                ret = 1
            else:
                raise
        return ret

    def __contains__(self, item):
        return item in self._storage

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            ret = self.__dict__ == other.__dict__
        else:
            ret = False
        return ret

    def __iter__(self):
        for key in self.keys():
            yield key

    def __getitem__(self, item):
        return self._storage[item]

    def __len__(self):
        return len(self._storage)

    def __setitem__(self, key, value):
        self._storage[key] = value

    def __repr__(self):
        ret = '{0}({1})'.format(self.__class__.__name__, [(k, v) for k, v in self.items()])
        return ret

    def __str__(self):
        return self.__repr__()

    def copy(self):
        ret = copy(self)
        ret._storage = ret._storage.copy()
        ret._storage_id = copy(ret._storage_id)
        return ret

    def first(self):
        for key in self.keys():
            return self._storage[key]

    def get(self, *args, **kwargs):
        return self._storage.get(*args, **kwargs)

    def items(self):
        return list(self._storage.items())

    def iteritems(self):
        for k, v in self._storage.items():
            yield k, v

    def iterkeys(self):
        for k in self._storage.keys():
            yield k

    def itervalues(self):
        for v in self._storage.values():
            yield v

    def keys(self):
        return list(self._storage.keys())

    def pop(self, *args, **kwargs):
        return self._storage.pop(*args, **kwargs)

    def update(self, dictionary):
        self._storage.update(dictionary)

    def values(self):
        return list(self._storage.values())
