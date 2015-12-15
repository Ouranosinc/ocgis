import itertools

import numpy as np
from shapely.geometry import Point

from ocgis.exc import EmptySubsetError
from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.grid import GridXY
from ocgis.new_interface.test.test_new_interface import AbstractTestNewInterface
from ocgis.new_interface.variable import Variable, BoundedVariable
from ocgis.util.helpers import make_poly, iter_array


class TestGridXY(AbstractTestNewInterface):
    def assertGridCorners(self, grid):
        """
        :type grid: :class:`ocgis.new_interface.grid.GridXY`
        """

        assert grid.corners is not None

        def _get_is_ascending_(arr):
            """
            Return ``True`` if the array is ascending from index 0 to -1.

            :type arr: :class:`numpy.ndarray`
            :rtype: bool
            """

            assert (arr.ndim == 1)
            if arr[0] < arr[-1]:
                ret = True
            else:
                ret = False

            return ret

        # Assert polygon constructed from grid corners contains the associated centroid value.
        for ii, jj in itertools.product(range(grid.shape[0]), range(grid.shape[1])):
            pt = Point(grid.value.data[1, ii, jj], grid.value.data[0, ii, jj])
            poly_corners = grid.corners.data[:, ii, jj]
            rtup = (poly_corners[0, :].min(), poly_corners[0, :].max())
            ctup = (poly_corners[1, :].min(), poly_corners[1, :].max())
            poly = make_poly(rtup, ctup)
            self.assertTrue(poly.contains(pt))

        # Assert masks are equivalent between value and corners.
        for (ii, jj), m in iter_array(grid.value.mask[0, :, :], return_value=True):
            if m:
                self.assertTrue(grid.corners.mask[:, ii, jj].all())
            else:
                self.assertFalse(grid.corners.mask[:, ii, jj].any())

        if grid.y is not None or grid.x is not None:
            self.assertEqual(_get_is_ascending_(grid.y.value), _get_is_ascending_(grid.corners.data[0, :, 0][:, 0]))
            self.assertEqual(_get_is_ascending_(grid.x.value), _get_is_ascending_(grid.corners.data[1, 0, :][:, 0]))

    def get_iter(self, return_kwargs=False):
        poss = [True, False]
        kwds = dict(with_2d_variables=poss,
                    with_dimensions=poss,
                    with_value=poss,
                    with_value_only=poss)
        for k in self.iter_product_keywords(kwds, as_namedtuple=False):
            ret = self.get_gridxy(**k)
            if return_kwargs:
                ret = (ret, k)
            yield ret

    def test_init(self):
        grid = self.get_gridxy()
        self.assertIsInstance(grid, GridXY)

        x = Variable('x', value=[1])
        with self.assertRaises(ValueError):
            GridXY(x=x)

        grid = self.get_gridxy(with_value=True)
        self.assertIsNotNone(grid._value)

    def test_corners(self):
        # Test constructing from x/y bounds.
        grid = self.get_gridxy()
        grid.x.set_extrapolated_bounds()
        grid.y.set_extrapolated_bounds()
        corners = grid.corners.copy()
        value = grid.value.copy()
        self.assertIsNotNone(corners)
        self.assertEqual(corners.shape, (2, grid.y.shape[0], grid.x.shape[0], 4))
        self.assertGridCorners(grid)

        # Test initializing corners with a value.
        grid = GridXY(value=value, corners=corners)
        self.assertNumpyAll(grid.corners, corners)

    def test_corners_esmf(self):
        x_bounds = Variable(value=[[-100.5, -99.5], [-99.5, -98.5], [-98.5, -97.5], [-97.5, -96.5]])
        x = BoundedVariable(value=[-100., -99., -98., -97.], bounds=x_bounds)

        y_bounds = Variable(value=[[40.5, 39.5], [39.5, 38.5], [38.5, 37.5]])
        y = BoundedVariable(value=[40., 39., 38.], bounds=y_bounds)

        grid = GridXY(x=x, y=y)

        actual = np.array([[[40.5, 40.5, 40.5, 40.5, 40.5], [39.5, 39.5, 39.5, 39.5, 39.5],
                            [38.5, 38.5, 38.5, 38.5, 38.5], [37.5, 37.5, 37.5, 37.5, 37.5]],
                           [[-100.5, -99.5, -98.5, -97.5, -96.5], [-100.5, -99.5, -98.5, -97.5, -96.5],
                            [-100.5, -99.5, -98.5, -97.5, -96.5], [-100.5, -99.5, -98.5, -97.5, -96.5]]],
                          dtype=grid.value.dtype)
        self.assertNumpyAll(actual, grid.corners_esmf)

    def test_dimensions(self):
        grid = self.get_gridxy()
        self.assertIsNone(grid.dimensions)

        grid = self.get_gridxy(with_dimensions=True)
        self.assertEqual(len(grid.dimensions), 2)
        self.assertEqual(grid.dimensions[0], Dimension('y', 4))

        grid = self.get_gridxy(with_dimensions=True, with_2d_variables=True)
        self.assertEqual(len(grid.dimensions), 2)
        self.assertEqual(grid.dimensions[0], Dimension('y', 4))

        grid = self.get_gridxy(with_value_only=True)
        self.assertIsNone(grid.x)
        self.assertIsNone(grid.y)
        self.assertIsNone(grid.dimensions)

    def test_getitem(self):
        for with_dimensions in [False, True]:
            grid = self.get_gridxy(with_dimensions=with_dimensions)
            self.assertEqual(grid.ndim, 2)
            sub = grid[2, 1]
            self.assertEqual(sub.x.value, 102.)
            self.assertEqual(sub.y.value, 42.)
            self.assertIsNone(grid._value)

            # Test with two-dimensional x and y values.
            grid = self.get_gridxy(with_2d_variables=True, with_dimensions=with_dimensions)
            sub = grid[1:3, 1:3]
            actual_x = [[102.0, 103.0], [102.0, 103.0]]
            self.assertEqual(sub.x.value.tolist(), actual_x)
            actual_y = [[41.0, 41.0], [42.0, 42.0]]
            self.assertEqual(sub.y.value.tolist(), actual_y)
            self.assertIsNone(grid._value)

        # Test with a value.
        grid = self.get_gridxy(with_value_only=True)
        sub = grid[1, :]
        self.assertEqual(sub.value.tolist(), [[[41.0, 41.0, 41.0]], [[101.0, 102.0, 103.0]]])

    def test_grid_get_subset_bbox(self):
        keywords = dict(bounds=[True, False], closed=[True, False])

        for k in self.iter_product_keywords(keywords):
            y = self.get_variable_y(bounds=k.bounds)
            x = self.get_variable_x(bounds=k.bounds)
            grid = GridXY(x=x, y=y)
            bg = grid.get_subset_bbox(-99, 39, -98, 39, closed=False)
            self.assertEqual(bg._value, None)
            with self.assertRaises(EmptySubsetError):
                grid.get_subset_bbox(1000, 1000, 1001, 10001, closed=k.closed)

            bg2 = grid.get_subset_bbox(-99999, 1, 1, 1000, closed=k.closed)
            self.assertNumpyAll(bg2.value, grid.value)

        # Test mask is not shared with subsetted grid.
        grid = self.get_gridxy(with_value_only=True)
        self.assertIsNone(grid.x)
        self.assertIsNone(grid.y)
        grid.value.mask[:, :, 1] = True
        args = (101.5, 40.5, 102.5, 42.5)
        sub = grid.get_subset_bbox(*args, use_bounds=False)
        self.assertTrue(np.all(sub.value.mask[:, 1, 0]))
        sub.value.mask[:, 0, 0] = False
        self.assertTrue(np.all(grid.value.mask[:, :, 1]))

    def test_resolution(self):
        for grid in self.get_iter():
            self.assertEqual(grid.resolution, 1.)

    def test_shape(self):
        for grid in self.get_iter():
            self.assertEqual(grid.shape, (4, 3))
            self.assertEqual(grid.ndim, 2)

    def test_value(self):
        for grid, kwds in self.get_iter(return_kwargs=True):
            try:
                self.assertIsNone(grid._value)
            except AssertionError:
                self.assertTrue(kwds['with_value'] or kwds['with_value_only'])
            value = grid.value
            self.assertEqual(value.shape, (2, 4, 3))
            self.assertTrue(np.all(grid.value[0, 1, :] == 41.))
            self.assertTrue(np.all(grid.value[1, :, 1] == 102.))

    def test_write_netcdf(self):
        grid = self.get_gridxy()
        path = self.get_temporary_file_path('out.nc')
        with self.nc_scope(path, 'w') as ds:
            grid.write_netcdf(ds)
        with self.nc_scope(path) as ds:
            var = ds.variables['y']
            self.assertNumpyAll(var[:], grid.y.value.data)

        # Test with 2-d x and y arrays.
        grid = self.get_gridxy(with_2d_variables=True, with_dimensions=True)
        path = self.get_temporary_file_path('out.nc')
        with self.nc_scope(path, 'w') as ds:
            grid.write_netcdf(ds)
        with self.nc_scope(path) as ds:
            var = ds.variables['y']
            self.assertNumpyAll(var[:], grid.y.value.data)

        # Test when the value is loaded.
        grid = self.get_gridxy(with_dimensions=True)
        grid._get_value_()
        path = self.get_temporary_file_path('out.nc')
        with self.nc_scope(path, 'w') as ds:
            grid.write_netcdf(ds)
        with self.nc_scope(path, 'r') as ds:
            self.assertEqual(['y', 'x'], [d for d in ds.variables['y'].dimensions])

        # Test with a value only.
        grid = self.get_gridxy(with_value_only=True)
        self.assertIsNone(grid.y)
        self.assertIsNone(grid.x)
        self.assertIsNone(grid.dimensions)
        dimensions = (Dimension('yy', 4), Dimension('xx', 3))
        grid.dimensions = dimensions
        with self.nc_scope(path, 'w') as ds:
            grid.write_netcdf(ds)
        with self.nc_scope(path, 'r') as ds:
            yc = ds.variables['yc']
            self.assertEqual(['yy', 'xx'], [d for d in yc.dimensions])
            self.assertEqual(yc.axis, 'Y')
