from copy import deepcopy

import numpy as np

from ocgis.util.helpers import get_bounds_from_1d
from ocgis.exc import VariableInCollectionError, VariableShapeMismatch, EmptySubsetError
from ocgis.api.collection import AbstractCollection
from ocgis import RequestDataset
from ocgis.interface.base.attributes import Attributes
from ocgis.new_interface.base import AbstractInterfaceObject
from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.test_new_interface import AbstractTestNewInterface
from ocgis.new_interface.variable import Variable, SourcedVariable, VariableCollection, BoundedVariable


class TestBoundedVariable(AbstractTestNewInterface):
    def get(self, with_bounds=True):
        value = np.array([4, 5, 6], dtype=float)
        if with_bounds:
            value_bounds = get_bounds_from_1d(value)
            bounds = Variable('x_bounds', value=value_bounds)
        else:
            bounds = None
        var = BoundedVariable('x', value=value, bounds=bounds)
        return var

    def test_bases(self):
        self.assertEqual(BoundedVariable.__bases__, (Variable,))

    def test_init(self):
        bv = self.get()
        self.assertEqual(bv.shape, (3,))

    def test_getitem(self):
        bv = self.get()
        sub = bv[1]
        self.assertNumpyAll(sub.bounds.value, bv.bounds[1, :].value)

    def test_get_between(self):
        bv = BoundedVariable('foo', value=[0])
        with self.assertRaises(EmptySubsetError):
            bv.get_between(100, 200)

        bv = BoundedVariable('foo', value=[100, 200, 300, 400])
        vdim_between = bv.get_between(100, 200)
        self.assertEqual(vdim_between.shape[0], 2)

    def test_get_between_bounds(self):
        value = [0., 5., 10.]
        bounds = [[-2.5, 2.5], [2.5, 7.5], [7.5, 12.5]]

        # # a reversed copy of these bounds are created here
        value_reverse = deepcopy(value)
        value_reverse.reverse()
        bounds_reverse = deepcopy(bounds)
        bounds_reverse.reverse()
        for ii in range(len(bounds)):
            bounds_reverse[ii].reverse()

        data = {'original': {'value': value, 'bounds': bounds},
                'reversed': {'value': value_reverse, 'bounds': bounds_reverse}}
        for key in ['original', 'reversed']:
            # vdim = VectorDimension(value=data[key]['value'],
            #                        bounds=data[key]['bounds'])
            bounds = Variable('hello_bounds', value=data[key]['bounds'])
            vdim = BoundedVariable('hello', value=data[key]['value'], bounds=bounds)

            vdim_between = vdim.get_between(1, 3)
            self.assertEqual(len(vdim_between), 2)
            if key == 'original':
                self.assertEqual(vdim_between.bounds.tostring(),
                                 '\x00\x00\x00\x00\x00\x00\x04\xc0\x00\x00\x00\x00\x00\x00\x04@\x00\x00\x00\x00\x00\x00\x04@\x00\x00\x00\x00\x00\x00\x1e@')
            else:
                self.assertEqual(vdim_between.bounds.tostring(),
                                 '\x00\x00\x00\x00\x00\x00\x1e@\x00\x00\x00\x00\x00\x00\x04@\x00\x00\x00\x00\x00\x00\x04@\x00\x00\x00\x00\x00\x00\x04\xc0')
            self.assertEqual(vdim.resolution, 5.0)

            ## preference is given to the lower bound in the case of "ties" where
            ## the value could be assumed part of the lower or upper cell
            vdim_between = vdim.get_between(2.5, 2.5)
            self.assertEqual(len(vdim_between), 1)
            if key == 'original':
                self.assertNumpyAll(vdim_between.bounds, np.array([[2.5, 7.5]]))
            else:
                self.assertNumpyAll(vdim_between.bounds, np.array([[7.5, 2.5]]))

            ## if the interval is closed and the subset range falls only on bounds
            ## value then the subset will be empty
            with self.assertRaises(EmptySubsetError):
                vdim.get_between(2.5, 2.5, closed=True)

            vdim_between = vdim.get_between(2.5, 7.5)
            if key == 'original':
                self.assertEqual(vdim_between.bounds.tostring(),
                                 '\x00\x00\x00\x00\x00\x00\x04@\x00\x00\x00\x00\x00\x00\x1e@\x00\x00\x00\x00\x00\x00\x1e@\x00\x00\x00\x00\x00\x00)@')
            else:
                self.assertEqual(vdim_between.bounds.tostring(),
                                 '\x00\x00\x00\x00\x00\x00)@\x00\x00\x00\x00\x00\x00\x1e@\x00\x00\x00\x00\x00\x00\x1e@\x00\x00\x00\x00\x00\x00\x04@')

    def test_get_between_use_bounds(self):
        value = [3., 5.]
        bounds = [[2., 4.], [4., 6.]]
        vdim = VectorDimension(value=value, bounds=bounds)
        ret = vdim.get_between(3, 4.5, use_bounds=False)
        self.assertNumpyAll(ret.value, np.array([3.]))
        self.assertNumpyAll(ret.bounds, np.array([[2., 4.]]))

    def test_set_extrapolated_bounds(self):
        bv = self.get(with_bounds=False)
        self.assertIsNone(bv.bounds)
        self.assertFalse(bv._has_extrapolated_bounds)
        bv.set_extrapolated_bounds()
        self.assertTrue(bv._has_extrapolated_bounds)
        self.assertEqual(bv.bounds.name, 'x_bounds')
        self.assertEqual(bv.bounds.ndim, 2)

    def test_write_netcdf(self):
        bv = self.get()
        dim_x = Dimension('x', 3)
        bv.dimensions = dim_x
        bv.bounds.dimensions = [dim_x, Dimension('bounds', 2)]
        path = self.get_temporary_file_path('out.nc')
        with self.nc_scope(path, 'w') as ds:
            bv.write_netcdf(ds)
        with self.nc_scope(path, 'r') as ds:
            var = ds.variables[bv.name]
            self.assertEqual(var.bounds, bv.bounds.name)


class TestSourcedVariable(AbstractTestNewInterface):
    def get(self, name='tas'):
        data = self.get_data()
        sv = SourcedVariable(name, data=data)
        self.assertIsNone(sv._value)
        self.assertIsNone(sv._dimensions)
        self.assertIsNone(sv._dtype)
        self.assertIsNone(sv._fill_value)
        self.assertIsNone(sv._attrs)
        return sv

    def get_data(self):
        data = self.test_data.get_rd('cancm4_tas')
        return data

    def test_bases(self):
        self.assertEqual(SourcedVariable.__bases__, (Variable,))

    def test_init(self):
        sv = self.get()
        self.assertIsInstance(sv._data, RequestDataset)

        sv = self.get(name='time_bnds')
        self.assertIsNone(sv._value)
        sub = sv[5:10, :]
        self.assertIsNone(sv._value)
        print sv.dimensions

    def test_getitem(self):
        sv = self.get()
        sub = sv[10:20, 5, 6]
        self.assertEqual(sub.shape, (10, 1, 1))
        self.assertIsNone(sub._value)
        self.assertIsNone(sub.dimensions[0].length)
        self.assertEqual(sub.dimensions[0].length_current, 10)

    def test_get_dimensions(self):
        sv = self.get()
        self.assertTrue(len(sv.dimensions), 3)

    def test_set_metadata_from_source_(self):
        sv = self.get()
        sv._set_metadata_from_source_()
        self.assertEqual(sv.dtype, np.float32)
        self.assertEqual(sv.fill_value, np.float32(1e20))
        dims = sv.dimensions
        self.assertIsNone(dims[0].length)
        self.assertEqual(dims[0].length_current, 3650)
        self.assertEqual(['time', 'lat', 'lon'], [d.name for d in dims])
        for d in dims:
            self.assertIsNone(d.__src_idx__)
        self.assertEqual(sv.attrs['standard_name'], 'air_temperature')

    def test_get_value_from_source_(self):
        sv = self.get()
        sub = sv[5:11, 3:6, 5:8]
        res = sub._get_value_from_source_()
        self.assertEqual(res.shape, (6, 3, 3))

        with self.nc_scope(self.get_data().uri, 'r') as ds:
            var = ds.variables[sv.name]
            actual = var[5:11, 3:6, 5:8]

        self.assertNumpyAll(res, actual)

    def test_value(self):
        sv = self.get()
        sub = sv[5:11, 3:6, 5:8]
        self.assertEqual(sub.value.shape, (6, 3, 3))


class TestVariable(AbstractTestNewInterface):
    def test_bases(self):
        self.assertEqual(Variable.__bases__, (AbstractInterfaceObject, Attributes))

    def get(self, return_original_data=True):
        value = [2, 3, 4, 5, 6, 7]
        time = Dimension('time', length=len(value))
        var = Variable('time_value', value=value, dimensions=time)
        if return_original_data:
            return time, value, var
        else:
            return var

    def test_init(self):
        time, value, var = self.get()

        self.assertEqual(var.dimensions, (time,))
        self.assertEqual(id(time), id(var.dimensions[0]))
        self.assertEqual(var.name, 'time_value')
        self.assertEqual(var.alias, var.name)
        self.assertEqual(var.shape, (len(value),))
        self.assertNumpyAll(var.value, np.ma.array(value))
        sub = var[2:4]
        self.assertIsInstance(sub, Variable)
        self.assertEqual(sub.shape, (2,))

        dtype = np.float32
        fill_value = 33.0
        var = Variable('foo', value=value, dimensions=time, dtype=dtype, fill_value=fill_value)
        self.assertEqual(var.dtype, dtype)
        self.assertEqual(var.value.dtype, dtype)
        self.assertEqual(var.value.fill_value, fill_value)

        var = Variable('foo')
        self.assertEqual(var.shape, tuple())
        self.assertIsNone(var.dimensions)

        var = Variable('foo', value=[4, 5, 6])
        self.assertEqual(var.shape, (3,))
        self.assertEqual(var.dtype, var.value.dtype)
        self.assertEqual(var.fill_value, var.value.fill_value)
        sub = var[1]
        self.assertEqual(sub.shape, (1,))

    def test_create_dimensions(self):
        var = Variable('tas', value=[4, 5, 6], dtype=float)
        self.assertIsNone(var.dimensions)
        var.create_dimensions('time')
        self.assertIsNotNone(var.dimensions)
        self.assertEqual(len(var.dimensions), 1)

    def test_write_netcdf(self):
        var = self.get(return_original_data=False)
        var.value.mask[1] = True
        var.attrs['axis'] = 'not_an_ally'
        path = self.get_temporary_file_path('out.nc')
        with self.nc_scope(path, 'w') as ds:
            var.write_netcdf(ds)
        with self.nc_scope(path) as ds:
            ncvar = ds.variables[var.name]
            self.assertEqual(ncvar.dtype, var.dtype)
            self.assertEqual(ncvar[:].fill_value, var.fill_value)
            self.assertEqual(ncvar.axis, 'not_an_ally')


class TestVariableCollection(AbstractTestNewInterface):
    def get(self):
        var1 = self.get_variable()
        var2 = self.get_variable(alias='wunderbar')
        vc = VariableCollection(variables=[var1, var2])
        return vc

    def get_variable(self, name='foo', alias='foobar'):
        dim = Dimension('x', length=3)
        value = [4, 5, 6]
        return Variable(name=name, alias=alias, dimensions=dim, value=value)

    def test_bases(self):
        self.assertEqual(VariableCollection.__bases__, (AbstractInterfaceObject, AbstractCollection,))

    def test_init(self):
        var1 = self.get_variable()

        vc = VariableCollection(variables=var1)
        self.assertEqual(len(vc), 1)

        var2 = self.get_variable()
        with self.assertRaises(VariableInCollectionError):
            VariableCollection(variables=[var1, var2])

        var2 = self.get_variable(alias='wunderbar')
        vc = VariableCollection(variables=[var1, var2])
        self.assertEqual(vc.keys(), ['foobar', 'wunderbar'])

        dim = Dimension('a', 4)
        var3 = Variable('bye', dimensions=dim, value=[4, 5, 6, 7])
        with self.assertRaises(VariableShapeMismatch):
            vc.add_variable(var3)

    def test_shape(self):
        vc = self.get()
        self.assertEqual(vc.shape, (3,))
