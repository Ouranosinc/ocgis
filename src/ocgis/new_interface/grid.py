import itertools
from collections import OrderedDict
from copy import copy

import numpy as np

from ocgis import constants
from ocgis.exc import EmptySubsetError
from ocgis.new_interface.adapter import SpatialAdapter
from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.variable import Variable, BoundedVariable
from ocgis.util.helpers import get_formatted_slice, get_reduced_slice, iter_array


class GridXY(Variable, SpatialAdapter):
    ndim = 2

    def __init__(self, **kwargs):
        self._corners = None
        self._x = None
        self._y = None

        try:
            self.y = kwargs.pop('y')
            self.x = kwargs.pop('x')
        except KeyError:
            if 'value' not in kwargs:
                msg = 'At least "x" and "y" are required to make a grid without a "value".'
                raise ValueError(msg)
        self.corners = kwargs.pop('corners', None)

        super(GridXY, self).__init__(**kwargs)

    def __getitem__(self, slc):
        """
        :param slc: The slice sequence with indices corresponding to:

         0 --> y-dimension
         1 --> x-dimension

        :type slc: sequence of slice-compatible arguments
        :returns: Sliced grid components.
        :rtype: :class:`ocgis.new_interface.grid.GridXY`
        """

        slc = get_formatted_slice(slc, self.ndim)
        ret = copy(self)
        if self._y is not None:
            if self.is_vectorized:
                ret.y = self.y[slc[0]]
                ret.x = self.x[slc[1]]
            else:
                ret.y = self.y[slc[0], slc[1]]
                ret.x = self.x[slc[0], slc[1]]
        if self._value is not None:
            ret.value = self._value[:, slc[0], slc[1]]
            ret.value.unshare_mask()
        if self._corners is not None:
            ret.corners = self.corners[:, slc[0], slc[1], :]
            ret.corners.unshare_mask()
        return ret

    @property
    def corners(self):
        """
        2 x row x column x 4

        2 = y, x or row, column
        row
        column
        4 = ul, ur, lr, ll
        """

        if self._corners is None:
            x_bounds_value = self._x.bounds.value
            y_bounds_value = self._y.bounds.value
            if x_bounds_value is None or y_bounds_value is None:
                pass
            else:
                fill = np.zeros([2] + list(self.shape) + [4], dtype=self.y.value.dtype)
                col_bounds = x_bounds_value
                row_bounds = y_bounds_value
                if self.y.ndim == 1:
                    for ii, jj in itertools.product(range(self.shape[0]), range(self.shape[1])):
                        fill_element = fill[:, ii, jj]
                        fill_element[:, 0] = row_bounds[ii, 0], col_bounds[jj, 0]
                        fill_element[:, 1] = row_bounds[ii, 0], col_bounds[jj, 1]
                        fill_element[:, 2] = row_bounds[ii, 1], col_bounds[jj, 1]
                        fill_element[:, 3] = row_bounds[ii, 1], col_bounds[jj, 0]
                else:
                    fill[0] = row_bounds
                    fill[1] = col_bounds

                # Copy the mask structure of the underlying value.
                mask_value = self.value.mask
                mask_fill = np.zeros(fill.shape, dtype=bool)
                for (ii, jj), m in iter_array(mask_value[0, :, :], return_value=True):
                    mask_fill[:, ii, jj, :] = m
                fill = np.ma.array(fill, mask=mask_fill)

                self._corners = fill

        return self._corners

    @corners.setter
    def corners(self, value):
        if value is not None:
            if not isinstance(value, np.ma.MaskedArray):
                value = np.ma.array(value, mask=False)
            assert value.ndim == 4
            assert value.shape[3] == 4
        self._corners = value

    @property
    def corners_esmf(self):
        fill = np.zeros([2] + [element + 1 for element in self.shape], dtype=self.value.dtype)
        range_row = range(self.shape[0])
        range_col = range(self.shape[1])
        _corners = self.corners.data
        for ii, jj in itertools.product(range_row, range_col):
            ref = fill[:, ii:ii + 2, jj:jj + 2]
            ref[:, 0, 0] = _corners[:, ii, jj, 0]
            ref[:, 0, 1] = _corners[:, ii, jj, 1]
            ref[:, 1, 1] = _corners[:, ii, jj, 2]
            ref[:, 1, 0] = _corners[:, ii, jj, 3]
        return fill

    @property
    def is_vectorized(self):
        y = self._y
        if y is not None and y.ndim == 1:
            ret = True
        else:
            ret = False

        return ret

    @property
    def x(self):
        if self._x is None:
            self._x = get_dimension_variable('X', self, 1, 'xc')
        return self._x

    @x.setter
    def x(self, value):
        assert isinstance(value, Variable)
        assert value.ndim <= 2
        self._x = value

    @property
    def y(self):
        if self._y is None:
            self._y = get_dimension_variable('Y', self, 1, 'yc')
        return self._y

    @y.setter
    def y(self, value):
        assert isinstance(value, Variable)
        assert value.ndim <= 2
        self._y = value

    @property
    def resolution(self):
        if self.is_vectorized:
            to_mean = [self.x.resolution, self.y.resolution]
        else:
            resolution_limit = int(constants.RESOLUTION_LIMIT) / 2
            r_value = self.value[:, 0:resolution_limit, 0:resolution_limit]
            rows = np.mean(np.diff(r_value[0, :, :], axis=0))
            cols = np.mean(np.diff(r_value[1, :, :], axis=1))
            to_mean = [rows, cols]
        ret = np.mean(to_mean)
        return ret

    @property
    def shape(self):
        if self._value is None:
            if self.is_vectorized:
                ret = [len(self.y), len(self.x)]
            else:
                ret = list(self.x.shape)
        else:
            ret = self.value.shape[1:]
        ret = tuple(ret)
        return ret

    def get_subset_bbox(self, min_col, min_row, max_col, max_row, return_indices=False, closed=True, use_bounds=True):
        assert min_row <= max_row
        assert min_col <= max_col

        if self.y.ndim == 2:
            assert not use_bounds
            r_row = self.value.data[0, :, :]
            real_idx_row = np.arange(0, r_row.shape[0])
            r_col = self.value.data[1, :, :]
            real_idx_col = np.arange(0, r_col.shape[1])

            if closed:
                lower_row = r_row > min_row
                upper_row = r_row < max_row
                lower_col = r_col > min_col
                upper_col = r_col < max_col
            else:
                lower_row = r_row >= min_row
                upper_row = r_row <= max_row
                lower_col = r_col >= min_col
                upper_col = r_col <= max_col

            idx_row = np.logical_and(lower_row, upper_row)
            idx_col = np.logical_and(lower_col, upper_col)

            keep_row = np.any(idx_row, axis=1)
            keep_col = np.any(idx_col, axis=0)

            # Slice reduction may fail due to empty bounding box returns. Catch these value errors and re-purpose as
            # subset errors.
            try:
                row_slc = get_reduced_slice(real_idx_row[keep_row])
            except ValueError:
                if real_idx_row[keep_row].shape[0] == 0:
                    raise EmptySubsetError(origin='Y')
                else:
                    raise
            try:
                col_slc = get_reduced_slice(real_idx_col[keep_col])
            except ValueError:
                if real_idx_col[keep_col].shape[0] == 0:
                    raise EmptySubsetError(origin='X')
                else:
                    raise
        else:
            new_row, row_indices = self.y.get_between(min_row, max_row, return_indices=True, closed=closed,
                                                      use_bounds=use_bounds)
            new_col, col_indices = self.x.get_between(min_col, max_col, return_indices=True, closed=closed,
                                                      use_bounds=use_bounds)
            row_slc = get_reduced_slice(row_indices)
            col_slc = get_reduced_slice(col_indices)

        ret = self[row_slc, col_slc]

        if return_indices:
            ret = (ret, (row_slc, col_slc))

        return ret

    def update_crs(self, to_crs):
        """
        Update the coordinate system in place.

        :param to_crs: The destination coordinate system.
        :type to_crs: :class:`ocgis.interface.base.crs.CoordinateReferenceSystem`
        """
        # tdk: finish
        assert self.crs is not None

        # Rotated pole transformations are a special case.
        if not isinstance(self.crs, CFRotatedPole) and not isinstance(to_crs, CFRotatedPole):
            # if the crs values are the same, pass through
            if to_crs != self.crs:
                to_sr = to_crs.sr

                if self.grid is not None:
                    # update grid values
                    value_row = self.grid.value.data[0].reshape(-1)
                    value_col = self.grid.value.data[1].reshape(-1)
                    self._update_crs_with_geometry_collection_(to_sr, value_row, value_col)
                    self.grid.value.data[0] = value_row.reshape(*self.grid.shape)
                    self.grid.value.data[1] = value_col.reshape(*self.grid.shape)

                    if self.grid.corners is not None:
                        # update the corners
                        corner_row = self.grid.corners.data[0].reshape(-1)
                        corner_col = self.grid.corners.data[1].reshape(-1)
                        self._update_crs_with_geometry_collection_(to_sr, corner_row, corner_col)

                    self.grid.row = None
                    self.grid.col = None

                if self._geom is not None:
                    if self.geom._point is not None:
                        self.geom.point.update_crs(to_crs, self.crs)
                    if self.geom._polygon is not None:
                        self.geom.polygon.update_crs(to_crs, self.crs)

                self.crs = to_crs
        else:
            try:
                """:type _crs: ocgis.interface.base.crs.CFRotatedPole"""
                new_spatial = self.crs.get_rotated_pole_transformation(self)
            # likely an inverse transformation if the destination crs is rotated pole.
            except AttributeError:
                new_spatial = to_crs.get_rotated_pole_transformation(self, inverse=True)
            self.__dict__ = new_spatial.__dict__
            self.crs = to_crs

    def write_netcdf(self, dataset, **kwargs):
        for tw in [self.y, self.x]:
            tw.write_netcdf(dataset, **kwargs)

    def _get_dimensions_(self):
        if self.is_vectorized:
            ret = (self.y.dimensions[0], self.x.dimensions[0])
        else:
            ret = self.y.dimensions
        return ret

    def _get_value_(self):
        if self._value is None:
            if self.is_vectorized:
                new_x, new_y = np.meshgrid(self.x.value, self.y.value)
                shp = (2, len(self.y), len(self.x))
            else:
                new_x, new_y = self.x.value, self.y.value
                shp = [2] + list(new_x.shape)

            fill = np.zeros(shp)
            fill[0, ...] = new_y
            fill[1, ...] = new_x

            self._set_value_(fill)

        return self._value

    def _validate_value_(self, value):
        if self._dimensions is not None and self._y is not None:
            assert value.shape[1:] == self.shape
            assert value.shape[0] == 2


def get_dimension_variable(axis_string, gridxy, idx, variable_name):
    if gridxy._dimensions is None:
        dim_y = Dimension('y', length=gridxy.shape[0])
        dim_x = Dimension('x', length=gridxy.shape[1])
    else:
        dim_y, dim_x = gridxy.dimensions
    attrs = OrderedDict({'axis': axis_string})
    # Only write the corners if they have been loaded.
    if gridxy._corners is not None:
        dim_n_corners = (Dimension('n_corners', length=4))
        corners = Variable(name='{}_corners'.format(variable_name), dimensions=(dim_y, dim_x, dim_n_corners),
                           value=gridxy.corners[idx, :, :, :])
        attrs.update({'bounds': corners.name})
    else:
        corners = None
    ret = BoundedVariable(name=variable_name, dimensions=(dim_y, dim_x), attrs=attrs,
                          bounds=corners, value=gridxy.value[idx, :, :])
    return ret