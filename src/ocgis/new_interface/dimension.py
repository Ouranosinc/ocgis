import numpy as np

from ocgis.new_interface.base import AbstractInterfaceObject
from ocgis.new_interface.mpi import OcgMpi, MPI_SIZE
from ocgis.util.helpers import get_formatted_slice


class Dimension(AbstractInterfaceObject):
    def __init__(self, name, length=None, length_current=None, dist=False):
        self._variable = None
        self._name = name
        self.length = length
        self.length_current = length_current
        self.dist = dist

        super(Dimension, self).__init__()

    def __eq__(self, other):
        if other.__dict__ == self.__dict__:
            ret = True
        else:
            ret = False
        return ret

    def __getitem__(self, slc):
        slc = get_formatted_slice(slc, 1)
        slc = slc[0]
        ret = self.copy()

        if ret._variable is not None:
            assert ret._variable.dimensions is None
            ret._variable = ret._variable[slc]

        try:
            length = len(slc)
        except TypeError:
            # Likely a slice object.
            try:
                length = slc.stop - slc.start
            except TypeError:
                # Likely a NoneType slice.
                if slc.start is None:
                    if slc.stop > 0:
                        length = len(self)
                    elif slc.stop is None:
                        length = len(self)
                    else:
                        length = len(self) + slc.stop
                elif slc.stop is None:
                    if slc.start > 0:
                        length = len(self) - slc.start
                    else:
                        length = abs(slc.start)
                else:
                    raise
        else:
            try:
                # Check for boolean slices.
                if slc.dtype == bool:
                    length = slc.sum()
            except AttributeError:
                # Likely a list/tuple.
                pass
        if self.length is None:
            if length < 0:
                # This is using negative indexing. Subtract from the current length.
                length = length + self.length_current
            ret.length_current = length
        else:
            if length < 0:
                # This is using negative indexing. Subtract from the current length.
                length = length + self.length
            ret.length = length
        return ret

    def __len__(self):
        if self.length is None:
            ret = self.length_current
        else:
            ret = self.length
        if ret is None:
            ret = 0
        return ret

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        msg = "{0}(name='{1}', length={2})".format(self.__class__.__name__, self.name, self.length)
        return msg

    @property
    def mpi(self):
        if MPI_SIZE > 0 and self.dist:
            # tdk: cache this object?
            ret = OcgMpi(len(self))
        else:
            ret = None
        return ret

    @property
    def name(self):
        return self._name

    @property
    def is_unlimited(self):
        if self.length is None:
            ret = True
        else:
            ret = False
        return ret


class SourcedDimension(Dimension):
    _default_dtype = np.int32

    def __init__(self, *args, **kwargs):
        src_idx = kwargs.pop('src_idx', None)

        if src_idx is not None:
            kwargs['length_current'] = len(src_idx)

        super(SourcedDimension, self).__init__(*args, **kwargs)

        if self.dist and self.mpi.bounds_local is None:
            self.__src_idx__ = None
        else:
            self.__src_idx__ = 'auto'
        self._src_idx = src_idx

    def __eq__(self, other):
        try:
            ret = super(SourcedDimension, self).__eq__(other)
        except ValueError:
            # Likely the source index is loaded which requires using a numpy comparison.
            ret = True
            for k, v in self.__dict__.iteritems():
                if k == '__src_idx__':
                    if not np.all(v == other.__dict__[k]):
                        ret = False
                        break
                else:
                    if v != other.__dict__[k]:
                        ret = False
                        break
        return ret

    def __getitem__(self, slc):
        ret = super(SourcedDimension, self).__getitem__(slc)
        ret._src_idx = self._src_idx.__getitem__(slc)
        return ret

    @property
    def _src_idx(self):
        if self.__src_idx__ is None:
            if self.dist:
                bounds = self.mpi.bounds_local
            else:
                bounds = (0, len(self))
            if bounds is not None:
                lower, upper = bounds
                self.__src_idx__ = np.arange(lower, upper, dtype=self._default_dtype)
        return self.__src_idx__

    @_src_idx.setter
    def _src_idx(self, value):
        if value is not None:
            if not isinstance(value, np.ndarray):
                value = np.array(value)
            if self.dist:
                bounds = self.mpi.bounds_local
                if bounds is None:
                    value = None
                else:
                    lower, upper = bounds
                    value = value[lower:upper]
        self.__src_idx__ = value
