import numpy as np

from ocgis.new_interface.base import AbstractInterfaceObject
from ocgis.new_interface.mpi import OcgMpi
from ocgis.util.helpers import get_formatted_slice


class Dimension(AbstractInterfaceObject):
    def __init__(self, name, length=None, length_current=None, dist=False):
        self._mpi = None
        self._name = name

        self.length = length
        self.length_current = length_current
        self.dist = dist

        super(Dimension, self).__init__()

        # If this dimension is distributed, some form of length is required.
        if self.dist:
            if self.length is None and self.length_current is None:
                msg = 'Distributed dimensions required "length" or "length_current".'
                raise ValueError(msg)

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
        if self._mpi is None:
            if self.dist:
                size = None
            else:
                size = 1
            self._mpi = OcgMpi(nelements=len(self), size=size)
        return self._mpi

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

    def gather(self, root=0):
        if self.mpi.size == 1:
            ret = self
        else:
            if self.mpi.rank == root:
                ret = self
            else:
                ret = None
        ret.dist = False
        return ret

    def scatter(self):
        self.dist = True
        self._mpi = None
        return self


class SourcedDimension(Dimension):
    _default_dtype = np.int32

    def __init__(self, *args, **kwargs):
        self.__src_idx__ = None
        src_idx = kwargs.pop('src_idx', None)

        if src_idx is not None:
            kwargs['length_current'] = len(src_idx)

        super(SourcedDimension, self).__init__(*args, **kwargs)

        self._src_idx = src_idx

    def __eq__(self, other):
        ret = True
        skip = ('__src_idx__', '_mpi')
        for k, v in self.__dict__.items():
            if k in skip:
                continue
            else:
                if v != other.__dict__[k]:
                    ret = False
                    break
        if ret:
            if self.__src_idx__ is not None or other.__src_idx__ is not None:
                if not np.all(self._src_idx == other.__src_idx__):
                    ret = False
        return ret

    def __getitem__(self, slc):
        ret = super(SourcedDimension, self).__getitem__(slc)
        ret._src_idx = self._src_idx.__getitem__(slc)
        return ret

    @property
    def _src_idx(self):
        if self.__src_idx__ is None and len(self) > 0:
            bounds = self.mpi.bounds_local
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

    def gather(self, root=0):
        ret = self
        if self.mpi.size != 1:
            bounds = self.mpi.comm.gather(self.mpi.bounds_local, root=root)
            src_indexes = self.mpi.comm.gather(self._src_idx, root=root)
            if self.mpi.rank == root:
                lower, upper = self.mpi.bounds_global
                src_idx = np.zeros((upper - lower,), dtype=self._default_dtype)
                for idx in range(self.mpi.size):
                    try:
                        lower, upper = bounds[idx]
                    except TypeError:
                        if bounds[idx] is not None:
                            raise
                    else:
                        src_idx[lower:upper] = src_indexes[idx]
                # This dimension is no longer distributed. Setting this to False will allow the local bounds to load
                # correctly.
                ret.dist = False
                ret._src_idx = src_idx
            else:
                ret = None
        else:
            ret.dist = False
        return ret

    def scatter(self):
        ret = super(SourcedDimension, self).scatter()
        # Reset the source index forcing a subset by local bounds if applicable for the rank.
        ret._src_idx = ret._src_idx
        return ret
