from copy import copy

import numpy as np

from ocgis.new_interface.base import AbstractInterfaceObject
from ocgis.new_interface.variable import Variable
from ocgis.util.helpers import get_formatted_slice


class Grid(AbstractInterfaceObject):
    # tdk: consider how to handle 1-dimensional x, y, z when expanded
    def __init__(self, x=None, y=None, z=None):
        self._mask = None

        self.x = x
        self.y = y
        self.z = z

        if self.x is None or self.y is None:
            msg = 'At least "x" and "y" are required to make a grid.'
            raise ValueError(msg)
        if self.x.ndim > 2 or self.y.ndim > 2:
            msg = '"x" and "y" may not have ndim > 2.'
            raise ValueError(msg)
        if self.z is not None and self.z.ndim > 3:
            msg = '"z" may not have ndim > 3.'
            raise ValueError(msg)

    def __getitem__(self, slc):
        """
        :param slc: The slice sequence with indices corresponding to:

         0 --> x-dimension
         1 --> y-dimension
         2 --> z-dimension (if present)

        :type slc: sequence of slice-compatible arguments
        :returns: Sliced grid components.
        :rtype: :class:`ocgis.new_interface.grid.Grid`
        """

        slc = get_formatted_slice(slc, self.ndim)
        ret = copy(self)
        if self.is_vectorized:
            ret.x = self.x[slc[0]]
            ret.y = self.y[slc[1]]
            if self.z is not None:
                ret.z = self.z[slc[2]]
        else:
            ret.x = self.x[slc[0], slc[1]]
            ret.y = self.y[slc[0], slc[1]]
            if self.z is not None:
                if self.z.ndim == 2:
                    ret.z = self.z[slc[0], slc[1]]
                else:
                    ret.z = self.z[slc[2], slc[0], slc[1]]
        return ret

    @property
    def is_vectorized(self):
        if len(self.x.shape) > 1:
            ret = False
        else:
            ret = True
        return ret

    @property
    def mask(self):
        if self.is_vectorized:
            self.expand()
        return self.x.value.mask

    @mask.setter
    def mask(self, value):
        if self.is_vectorized:
            self.expand()
        self.x.mask = value
        self.y.mask = value

    @property
    def ndim(self):
        if self.z is None:
            ret = 2
        else:
            ret = 3
        return ret

    @property
    def resolution(self):
        ret = np.mean([self.x.resolution, self.y.resolution])
        return ret

    @property
    def shape(self):
        if self.is_vectorized:
            ret = [len(self.y), len(self.x)]
            if self.z is not None:
                ret.append(len(self.z))
        else:
            ret = list(self.x.shape)
            if self.z is not None:
                if self.z.ndim == 1:
                    zshp = self.z.shape[0]
                elif self.z.ndim == 2:
                    zshp = 1
                else:
                    zshp = self.z.shape[0]
                ret.append(zshp)
        ret = tuple(ret)
        return ret

    def expand(self):
        # tdk: test with z
        assert self.x.ndim == 1
        assert self.y.ndim == 1

        new_x, new_y = np.meshgrid(self.x.value, self.y.value)

        if self.x.dimensions is not None:
            new_dims = (self.y.dimensions[0], self.x.dimensions[0])
        else:
            new_dims = None

        self.x = Variable(self.x.name, value=new_x, dimensions=new_dims)
        self.y = Variable(self.y.name, value=new_y, dimensions=new_dims)

        self.x.value.mask = self.y.value.mask

    def write_netcdf(self, dataset, **kwargs):
        to_write = [self.x, self.y]
        if self.z is not None:
            to_write.append(self.z)
        for tw in to_write:
            tw.write_netcdf(dataset, **kwargs)

    def validate_mask(self):
        # tdk: implement
        raise NotImplementedError
