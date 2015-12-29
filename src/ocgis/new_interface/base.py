from abc import ABCMeta, abstractmethod


class AbstractInterfaceObject(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def copy(self):
        """Return a shallow copy of self."""

    @abstractmethod
    def write_netcdf(self, *args, **kwargs):
        """Write to an open NetCDF dataset object."""


def get_keyword_arguments_from_template_keys(kwargs, keys, ignore_self=True, pop=False):
    ret = {}
    for key in keys:
        if ignore_self and key == 'self':
            continue
        try:
            if pop:
                ret[key] = kwargs.pop(key)
            else:
                ret[key] = kwargs[key]
        except KeyError:
            # Pass on key errors to allow classes to overload default keyword argument values.
            pass
    return ret
