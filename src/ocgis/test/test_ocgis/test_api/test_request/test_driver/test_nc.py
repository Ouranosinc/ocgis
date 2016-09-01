import datetime
import os
import pickle
import shutil
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime as dt
from unittest import SkipTest

import fiona
import netCDF4 as nc
import numpy as np
from shapely.geometry.geo import shape

import ocgis
from ocgis import GeomCabinet
from ocgis import RequestDataset
from ocgis import env
from ocgis.api.request.driver.base import iter_all_group_keys, get_group
from ocgis.api.request.driver.nc import DriverNetcdf, DriverNetcdfCF
from ocgis.constants import MPIDistributionMode
from ocgis.exc import EmptySubsetError, DimensionNotFound, OcgWarning, CannotFormatTimeError, \
    NoDimensionedVariablesFound
from ocgis.interface.base.crs import WGS84, CFWGS84, CFLambertConformal, CoordinateReferenceSystem, CFSpherical
from ocgis.interface.base.dimension.base import VectorDimension
from ocgis.interface.base.dimension.spatial import SpatialGeometryPolygonDimension, SpatialGeometryDimension, \
    SpatialDimension
from ocgis.interface.metadata import NcMetadata
from ocgis.interface.nc.spatial import NcSpatialGridDimension
from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.field import OcgField
from ocgis.new_interface.mpi import MPI_RANK, MPI_COMM, OcgMpi, variable_scatter, MPI_SIZE
from ocgis.new_interface.temporal import TemporalVariable
from ocgis.new_interface.variable import Variable, ObjectType, VariableCollection
from ocgis.test.base import TestBase, nc_scope, attr
from ocgis.util.units import get_units_object


#tdk: clean-up

class TestDriverNetcdf(TestBase):
    def test_init(self):
        path = self.get_temporary_file_path('foo.nc')
        with self.nc_scope(path, 'w') as ds:
            ds.createDimension('a', 2)
        rd = RequestDataset(uri=path, driver='netcdf')
        self.assertIsInstance(rd.driver, DriverNetcdf)
        vc = rd.get_variable_collection()
        self.assertEqual(len(vc), 0)

    def test_get_dist(self):

        def _create_dimensions_(ds, k):
            if k.dim_count > 0:
                ds.createDimension('one', 1)
                if k.dim_count == 2:
                    ds.createDimension('two', 2)

        kwds = dict(dim_count=[0, 1, 2], nested=[False, True])
        for k in self.iter_product_keywords(kwds):
            path = self.get_temporary_file_path('{}.nc'.format(k.dim_count))
            with self.nc_scope(path, 'w') as ds:
                _create_dimensions_(ds, k)
                if k.nested:
                    group1 = ds.createGroup('nest1')
                    _create_dimensions_(group1, k)
                    group2 = group1.createGroup('nest2')
                    _create_dimensions_(group2, k)
                    group3 = group2.createGroup('nest1')
                    _create_dimensions_(group3, k)
                    group3a = group2.createGroup('nest3')
                    _create_dimensions_(group3a, k)
                    group3.createDimension('outlier', 4)
            rd = RequestDataset(uri=path)
            driver = DriverNetcdf(rd)

            actual = driver.get_dist().mapping

            # All dimensions are not distributed.
            for keyseq in iter_all_group_keys(actual[MPI_RANK]):
                group = get_group(actual[MPI_RANK], keyseq)
                for dim in group['dimensions'].values():
                    self.assertFalse(dim.dist)

            if k.dim_count == 0 and k.nested:
                desired = {None: {'variables': {}, 'dimensions': {}, 'groups': {
                    u'nest1': {'variables': {}, 'dimensions': {}, 'groups': {
                        u'nest2': {'variables': {}, 'dimensions': {}, 'groups': {u'nest1': {'variables': {},
                                                                                            'dimensions': {
                                                                                                u'outlier': Dimension(
                                                                                                    name='outlier',
                                                                                                    size=4,
                                                                                                    size_current=4,
                                                                                                    dist=False,
                                                                                                    src_idx='auto')},
                                                                                            'groups': {}}}}}}}}}
                self.assertEqual(actual[MPI_RANK], desired)

            if k.dim_count == 2 and k.nested:
                self.assertIsNotNone(driver.metadata_source['groups']['nest1']['groups']['nest2'])
                two_dimensions = [Dimension(name='one', size=1, size_current=1),
                                  Dimension(name='two', size=2, size_current=2)]
                nest1 = {'dimensions': two_dimensions, 'groups': {}}
                template = deepcopy(nest1)
                nest1['groups']['nest2'] = deepcopy(template)
                nest1['groups']['nest2']['groups']['nest1'] = deepcopy(template)
                nest1['groups']['nest2']['groups']['nest3'] = deepcopy(template)
                nest1['groups']['nest2']['groups']['nest1']['dimensions'].append(Dimension('outlier', 4))
                desired = {None: {'dimensions': two_dimensions, 'groups': {u'nest1': nest1}}}
                groups_actual = list(iter_all_group_keys((actual[MPI_RANK])))
                groups_desired = list(iter_all_group_keys(desired))
                self.assertEqual(groups_actual, groups_desired)

    def test_get_dump_report(self):
        # Test with nested groups.
        path = self.get_temporary_file_path('foo.nc')
        with self.nc_scope(path, 'w') as ds:
            ds.convention = 'CF Free-For-All 0.99'
            ds.createDimension('dim_root', 5)
            var1_root = ds.createVariable('var1_root', float, dimensions=('dim_root',))
            var1_root.who_knew = 'I did not.'

            group1 = ds.createGroup('group1')
            group1.createDimension('dim_group1', 7)
            var1_group1 = group1.createVariable('var1_group1', int, dimensions=('dim_group1',))
            var1_group1.whatever = 'End of the line!'

            group1_group1 = group1.createGroup('group1_group1')
            group1_group1.createDimension('dim_group1_group1', 10)
            var1_group1_group1 = group1_group1.createVariable('bitter_end', float, dimensions=('dim_group1_group1',))
            var1_group1_group1.foo = 70

        rd = RequestDataset(path)
        driver = DriverNetcdf(rd)
        lines = driver.get_dump_report()
        desired = ['OCGIS Driver Key: netcdf {', 'dimensions:', '    dim_root = 5 ;', 'variables:',
                   '    float64 var1_root(dim_root) ;', '      var1_root:who_knew = "I did not." ;', '',
                   '// global attributes:', '    :convention = "CF Free-For-All 0.99" ;', '', u'group: group1 {',
                   '  dimensions:', '      dim_group1 = 7 ;', '  variables:', '      int64 var1_group1(dim_group1) ;',
                   '        var1_group1:whatever = "End of the line!" ;', '', u'  group: group1_group1 {',
                   '    dimensions:', '        dim_group1_group1 = 10 ;', '    variables:',
                   '        float64 bitter_end(dim_group1_group1) ;', '          bitter_end:foo = 70 ;',
                   '    } // group: group1_group1', '  } // group: group1', '}']
        self.assertEqual(lines, desired)

    def test_open(self):
        # Test with a multi-file dataset.
        path1 = self.get_temporary_file_path('foo1.nc')
        path2 = self.get_temporary_file_path('foo2.nc')
        for idx, path in enumerate([path1, path2]):
            with self.nc_scope(path, 'w', format='NETCDF4_CLASSIC') as ds:
                ds.createDimension('a', None)
                b = ds.createVariable('b', np.int32, ('a',))
                b[:] = idx
        uri = [path1, path2]
        rd = RequestDataset(uri=uri, driver=DriverNetcdf)
        field = rd.get_variable_collection()
        self.assertEqual(field['b'].value.tolist(), [0, 1])

    @attr('mpi')
    def test_write_variable_collection(self):
        if MPI_RANK == 0:
            path_in = self.get_temporary_file_path('foo.nc')
            path_out = self.get_temporary_file_path('foo_out.nc')
            with self.nc_scope(path_in, 'w') as ds:
                ds.createDimension('seven', 7)
                var = ds.createVariable('var_seven', float, dimensions=('seven',))
                var[:] = np.arange(7, dtype=float) + 10
                var.foo = 'bar'
        else:
            path_in, path_out = [None] * 2
        path_in = MPI_COMM.bcast(path_in)
        path_out = MPI_COMM.bcast(path_out)

        rd = RequestDataset(path_in)
        rd.metadata['dimensions']['seven']['dist'] = True
        driver = DriverNetcdf(rd)
        vc = driver.get_variable_collection()
        vc.write(path_out)

        if MPI_RANK == 0:
            self.assertNcEqual(path_in, path_out)

        MPI_COMM.Barrier()

    @attr('mpi')
    def test_write_variable_collection_isolated_variables(self):
        """Test writing a variable collection containing an isolated variable."""

        if MPI_SIZE < 4:
            raise SkipTest('MPI procs < 4')

        if MPI_RANK == 0:
            path_in = self.get_temporary_file_path('foo.nc')
            path_out = self.get_temporary_file_path('foo_out.nc')
            with self.nc_scope(path_in, 'w') as ds:
                ds.createDimension('seven', 7)
                var = ds.createVariable('var_seven', float, dimensions=('seven',))
                var[:] = np.arange(7, dtype=float) + 10
                var.foo = 'bar'
        else:
            path_in, path_out = [None] * 2
        path_in = MPI_COMM.bcast(path_in)
        path_out = MPI_COMM.bcast(path_out)

        rd = RequestDataset(path_in)
        rd.metadata['variables']['var_seven']['dist'] = MPIDistributionMode.ISOLATED
        ranks = (1, 3)
        # dist_rank = (0,)
        rd.metadata['variables']['var_seven']['ranks'] = ranks

        vc = rd.get_variable_collection()
        actual = vc['var_seven']
        self.assertIsNotNone(actual.dist)

        if MPI_RANK in ranks:
            self.assertFalse(actual.is_empty)
            self.assertIsNotNone(actual.value)
        else:
            self.assertTrue(actual.is_empty)
            self.assertIsNone(actual._value)
            self.assertIsNone(actual.value)

        vc.write(path_out)

        self.assertNcEqual(path_in, path_out)

        MPI_COMM.Barrier()

    def test_write_variable_collection_dataset_variable_kwargs(self):
        """Test writing while overloading things like the dataset data model."""

        path_in = self.get_temporary_file_path('foo.nc')
        path_out = self.get_temporary_file_path('foo_out.nc')
        with self.nc_scope(path_in, 'w', format='NETCDF3_CLASSIC') as ds:
            ds.createDimension('seven', 7)
            var = ds.createVariable('var_seven', np.float32, dimensions=('seven',))
            var[:] = np.arange(7, dtype=np.float32) + 10
            var.foo = 'bar'

        rd = RequestDataset(path_in)
        driver = DriverNetcdf(rd)
        vc = driver.get_variable_collection()
        vc.write(path_out, dataset_kwargs={'format': 'NETCDF3_CLASSIC'}, variable_kwargs={'zlib': True})

        self.assertNcEqual(path_in, path_out)

    @attr('mpi')
    def test_write_variable_collection_object_arrays(self):
        """Test writing variable length arrays in parallel."""

        if MPI_RANK == 0:
            path_actual = self.get_temporary_file_path('in.nc')
            path_desired = self.get_temporary_file_path('out.nc')

            value = [[1, 3, 5],
                     [7, 9],
                     [11]]
            v = Variable(name='objects', value=value, fill_value=4, dtype=ObjectType(int), dimensions='values')

            with self.nc_scope(path_desired, 'w') as ds:
                v.write(ds)
        else:
            v, path_actual, path_desired = [None] * 3
        path_actual = MPI_COMM.bcast(path_actual)
        path_desired = MPI_COMM.bcast(path_desired)

        dest_mpi = OcgMpi()
        dest_mpi.create_dimension('values', 3, dist=True)
        dest_mpi.update_dimension_bounds()

        scattered, _ = variable_scatter(v, dest_mpi)
        outvc = VariableCollection(variables=[scattered])
        outvc.write(path_actual)

        if MPI_RANK == 0:
            self.assertNcEqual(path_actual, path_desired)

        MPI_COMM.Barrier()


class TestDriverNetcdfCF(TestBase):

    def get_drivernetcdf(self, **kwargs):
        path = self.get_drivernetcdf_file_path()
        kwargs['uri'] = path
        rd = RequestDataset(**kwargs)
        d = DriverNetcdfCF(rd)
        return d

    def get_drivernetcdf_file_path(self):
        path = self.get_temporary_file_path('drivernetcdf.nc')
        with self.nc_scope(path, 'w') as ds:
            ds.convention = 'CF-1.6'
            ds.createDimension('time')
            ds.createDimension('x', 5)
            ds.createDimension('bounds', 2)

            vx = ds.createVariable('x', np.float32, dimensions=['time', 'x'])
            vx[:] = np.random.rand(3, 5) * 100
            vx.grid_mapping = 'latitude_longitude'

            crs = ds.createVariable('latitude_longitude', np.int8)
            crs.grid_mapping_name = 'latitude_longitude'

            vt = ds.createVariable('time', np.float32, dimensions=['time'])
            vt.axis = 'T'
            vt.climatology = 'time_bounds'
            vt[:] = np.arange(1, 4)
            vtb = ds.createVariable('time_bounds', np.float32, dimensions=['time', 'bounds'])
            vtb[:] = [[0.5, 1.5], [1.5, 2.5], [2.5, 3.5]]

            group1 = ds.createGroup('group1')
            group1.contact = 'email'
            group1.createDimension('y', 4)
            vy = group1.createVariable('y', np.int16, dimensions=['y'])
            vy.scale_factor = 5.0
            vy.add_offset = 100.0
            vy[:] = np.ma.array([1, 2, 3, 4], mask=[False, True, False, False])
        return path

    def get_2d_state_boundaries(self):
        geoms = []
        build = True
        sc = GeomCabinet()
        path = sc.get_shp_path('state_boundaries')
        with fiona.open(path, 'r') as source:
            for ii, row in enumerate(source):
                if build:
                    nrows = len(source)
                    dtype = []
                    for k, v in source.schema['properties'].iteritems():
                        if v.startswith('str'):
                            v = str('|S{0}'.format(v.split(':')[1]))
                        else:
                            v = getattr(np, v.split(':')[0])
                        dtype.append((str(k), v))
                    fill = np.empty(nrows, dtype=dtype)
                    ref_names = fill.dtype.names
                    build = False
                fill[ii] = tuple([row['properties'][n] for n in ref_names])
                geoms.append(shape(row['geometry']))
        geoms = np.atleast_2d(geoms)
        return geoms, fill

    def get_2d_state_boundaries_sdim(self):
        geoms, attrs = self.get_2d_state_boundaries()
        poly = SpatialGeometryPolygonDimension(value=geoms)
        geom = SpatialGeometryDimension(polygon=poly)
        sdim = SpatialDimension(geom=geom, properties=attrs, crs=WGS84())
        return sdim

    def test_init(self):
        d = self.get_drivernetcdf()
        self.assertIsInstance(d, DriverNetcdf)

    @attr('data')
    def test_system_cf_data_read(self):
        """Test some basic reading operations."""

        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        self.assertIsInstance(field, OcgField)
        self.assertEqual(rd.variable, 'tas')
        self.assertEqual(field['tas'].units, 'K')
        self.assertEqual(len(field.dimensions), 4)

        # Test overloading units.
        path = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(uri=path, units='celsius')
        field = rd.get()
        self.assertEqual(field['tas'].units, 'celsius')

    @attr('data', 'mpi')
    def test_system_cf_data_write_parallel(self):
        """Test some basic reading operations."""

        if MPI_RANK == 0:
            path_out = self.get_temporary_file_path('foo.nc')
        else:
            path_out = None
        path_out = MPI_COMM.bcast(path_out)

        rd = self.test_data.get_rd('cancm4_tas')
        rd.metadata['dimensions']['lat']['dist'] = True
        rd.metadata['dimensions']['lon']['dist'] = True
        field = rd.get()
        field.write(path_out, dataset_kwargs={'format': rd.metadata['file_format']})

        if MPI_RANK == 0:
            ignore_attributes = {'time_bnds': ['units', 'calendar'], 'lat_bnds': ['units'], 'lon_bnds': ['units']}
            self.assertNcEqual(path_out, rd.uri, ignore_variables=['latitude_longitude'],
                               ignore_attributes=ignore_attributes)

    def test_dimension_map(self):
        # Test overloaded dimension map from request dataset is used.
        dm = {'level': {'variable': 'does_not_exist'}}
        driver = self.get_drivernetcdf(dimension_map=dm)
        self.assertDictEqual(driver.rd.dimension_map, dm)
        # The driver dimension map always loads from the data.
        self.assertNotEqual(driver.dimension_map, dm)
        self.assertNotEqual(dm, driver.get_dimension_map(driver.metadata_source))
        field = driver.get_field()
        self.assertIsNone(field.time)

    def test_get_dimensioned_variables(self):
        driver = self.get_drivernetcdf()
        dvars = driver.get_dimensioned_variables(driver.dimension_map, driver.metadata_source)
        self.assertEqual(len(dvars), 0)

        # Test a found variable.
        dimension_map = {'time': {'variable': 'the_time', 'names': ['tt', 'ttt']},
                         'x': {'variable': 'xx', 'names': ['xx', 'xxx']},
                         'y': {'variable': 'yy', 'names': ['yy', 'yyy']}}
        metadata = {'variables': {'tas': {'dimensions': ('xx', 'ttt', 'yyy')},
                                  'pr': {'dimensions': ('foo',)}}}
        dvars = driver.get_dimensioned_variables(dimension_map, metadata)
        self.assertEqual(dvars, ['tas'])

        # Test request dataset uses the dimensioned variables.
        driver = self.get_drivernetcdf()
        with self.assertRaises(NoDimensionedVariablesFound):
            assert driver.rd.variable

    def test_get_field(self):
        # tdk: test that one-dimensional subsets are applied
        driver = self.get_drivernetcdf()
        field = driver.get_field(format_time=False)
        self.assertIsInstance(field.time, TemporalVariable)
        with self.assertRaises(CannotFormatTimeError):
            assert field.time.value_datetime
        self.assertIsInstance(field.crs, CoordinateReferenceSystem)

        # Test overloading the coordinate system.
        path = self.get_temporary_file_path('foo.nc')
        with self.nc_scope(path, 'w') as ds:
            v = ds.createVariable('latitude_longitude', np.int)
            v.grid_mapping_name = 'latitude_longitude'
        # First, test the default is found.
        rd = RequestDataset(uri=path)
        driver = DriverNetcdfCF(rd)
        self.assertEqual(driver.crs, CFSpherical())
        self.assertEqual(driver.get_field().crs, CFSpherical())
        # Second, test the overloaded CRS is found.
        desired = CoordinateReferenceSystem(epsg=2136)
        rd = RequestDataset(uri=path, crs=desired)
        self.assertEqual(rd.crs, desired)
        driver = DriverNetcdfCF(rd)
        self.assertEqual(driver.crs, CFSpherical())
        field = driver.get_field()
        self.assertEqual(field.crs, desired)
        # Test file coordinate system variable is removed.
        self.assertNotIn('latitude_longitude', field)

        # Test the default coordinate system is used when nothing is in the file.
        path = self.get_temporary_file_path('foo.nc')
        with self.nc_scope(path, 'w') as ds:
            ds.createVariable('nothing', np.int)
        rd = RequestDataset(uri=path)
        driver = DriverNetcdfCF(rd)
        self.assertEqual(rd.crs, env.DEFAULT_COORDSYS)
        self.assertEqual(driver.crs, env.DEFAULT_COORDSYS)
        self.assertEqual(driver.get_field().crs, env.DEFAULT_COORDSYS)

    def test_metadata_raw(self):
        d = self.get_drivernetcdf()
        metadata = d.metadata_raw
        self.assertIsInstance(metadata, dict)

        desired = metadata.copy()
        pickled = pickle.dumps(metadata)
        unpickled = pickle.loads(pickled)
        self.assertEqual(unpickled, desired)

    def test_get_dump_report(self):
        d = self.get_drivernetcdf()
        r = d.get_dump_report()
        self.assertGreaterEqual(len(r), 24)

    def test_get_dimension_map(self):
        d = self.get_drivernetcdf()
        dmap = d.get_dimension_map(d.metadata_source)
        desired = {'crs': {'variable': 'latitude_longitude'},
                   'time': {'variable': u'time', 'bounds': u'time_bounds', 'names': ['time'], 'dist': False}}
        self.assertEqual(dmap, desired)

        def _run_():
            env.SUPPRESS_WARNINGS = False
            metadata = {'variables': {'x': {'name': 'x',
                                            'attributes': {'axis': 'X', 'bounds': 'x_bounds'},
                                            'dimensions': ('xx',)}},
                        'dimensions': {'xx': {'name': 'xx', 'size': None}}}
            d.get_dimension_map(metadata)

        self.assertWarns(OcgWarning, _run_)

        # Test pulling distributed dimensions from metadata.
        d = self.get_drivernetcdf()
        self.assertIsNone(d._dimension_map)
        d.metadata_source['dimensions']['time']['dist'] = True
        dmap = d.dimension_map
        self.assertTrue(dmap['time']['dist'])

    def test_tdk(self):
        # Test only one distributed dimension allowed.
        d = self.get_drivernetcdf()
        self.assertIsNone(d._dimension_map)
        d.metadata_source['dimensions']['time']['dist'] = True
        d.metadata_source['dimensions']['x']['dist'] = True
        with self.assertRaises(ValueError):
            _ = d.dimension_map


class OldTestDriverNetcdf(TestBase):
    def setUp(self):
        raise SkipTest('old driver netcdf tests')

    @attr('data')
    def test_get_dimensioned_variables_one_variable_in_target_dataset(self):
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(uri=uri)
        driver = DriverNetcdf(rd)
        ret = driver.get_dimensioned_variables()
        self.assertEqual(ret, ['tas'])
        self.assertEqual(rd.variable, ret[0])

    @attr('data')
    def test_get_dimensioned_variables_two_variables_in_target_dataset(self):
        rd_orig = self.test_data.get_rd('cancm4_tas')
        dest_uri = os.path.join(self.current_dir_output, os.path.split(rd_orig.uri)[1])
        shutil.copy2(rd_orig.uri, dest_uri)
        with nc_scope(dest_uri, 'a') as ds:
            var = ds.variables['tas']
            outvar = ds.createVariable(var._name + 'max', var.dtype, var.dimensions)
            outvar[:] = var[:] + 3
            outvar.setncatts(var.__dict__)
        rd = RequestDataset(uri=dest_uri)
        self.assertEqual(rd.variable, ('tas', 'tasmax'))
        self.assertEqual(rd.variable, rd.alias)

    # @attr('data')
    # def test_get_dump_report(self):
    #     rd = self.test_data.get_rd('cancm4_tas')
    #     driver = DriverNetcdf(rd)
    #     self.assertTrue(len(driver.get_dump_report()) > 15)

    @attr('data')
    def test_get_field(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri)
        field = rd.get()

        self.assertIsInstance(field.spatial.grid, NcSpatialGridDimension)

        # Test names are correctly set when creating the field.
        self.assertEqual(field.temporal.name, 'time')
        self.assertEqual(field.temporal.name_value, 'time')
        self.assertEqual(field.temporal.name_bounds, 'time_bnds')
        row = field.spatial.grid.row
        self.assertEqual(row.name, 'lat')
        self.assertEqual(row.name_value, 'lat')
        self.assertEqual(row.name_bounds, 'lat_bnds')
        col = field.spatial.grid.col
        self.assertEqual(col.name, 'lon')
        self.assertEqual(col.name_value, 'lon')
        self.assertEqual(col.name_bounds, 'lon_bnds')

        # Test attributes are loaded.
        self.assertEqual(len(field.attrs), 31)
        self.assertEqual(len(field.variables['tas'].attrs), 10)
        self.assertEqual(len(field.temporal.attrs), 6)
        self.assertEqual(len(field.spatial.grid.row.attrs), 5)
        self.assertEqual(len(field.spatial.grid.col.attrs), 5)

        with self.nc_scope(uri) as ds:
            self.assertEqual(field.level, None)
            self.assertEqual(field.spatial.crs, WGS84())

            tv = field.temporal.value
            test_tv = ds.variables['time'][:]
            self.assertNumpyAll(tv, test_tv)
            self.assertNumpyAll(field.temporal.bounds, ds.variables['time_bnds'][:])

            tdt = field.temporal.value_datetime
            self.assertEqual(tdt[4], dt(2001, 1, 5, 12))
            self.assertNumpyAll(field.temporal.bounds_datetime[1001], np.array([dt(2003, 9, 29), dt(2003, 9, 30)]))

            rv = field.temporal.value_datetime[100]
            rb = field.temporal.bounds_datetime[100]
            self.assertTrue(all([rv > rb[0], rv < rb[1]]))

            self.assertEqual(field.temporal.extent_datetime,
                             (datetime.datetime(2001, 1, 1), datetime.datetime(2011, 1, 1)))

    @attr('data')
    def test_get_field_t_conform_units_to(self):
        """
        Test conforming time units is appropriately passed to field object.
        """

        uri = self.test_data.get_uri('cancm4_tas')
        target = get_units_object('days since 1949-1-1', calendar='365_day')
        rd = RequestDataset(uri=uri, t_conform_units_to=target)
        field = rd.get()
        self.assertEqual(field.temporal.conform_units_to, target)

    def test_get_field_different_dimension_names_and_values(self):
        """Test dimension names and dimension values are correctly read from netCDF."""

        path = os.path.join(self.current_dir_output, 'foo.nc')
        with nc_scope(path, 'w') as ds:
            ds.createDimension('lat', 1)
            ds.createDimension('lon', 1)
            ds.createDimension('tme', 1)
            ds.createDimension('the_bounds', 2)
            latitude = ds.createVariable('latitude', int, dimensions=('lat',))
            longitude = ds.createVariable('longitude', int, dimensions=('lon',))
            time = ds.createVariable('time', int, dimensions=('tme',))
            time_bounds = ds.createVariable('long_live_the_bounds', int, dimensions=('tme', 'the_bounds'))
            time.units = 'days since 0000-01-01'
            time.bounds = 'long_live_the_bounds'
            value = ds.createVariable('value', int, dimensions=('tme', 'lat', 'lon'))

            latitude[:] = 5
            longitude[:] = 6
            time[:] = 6
            value[:] = np.array([7]).reshape(1, 1, 1)

        rd = RequestDataset(path)
        driver = DriverNetcdf(rd)
        field = driver._get_field_()
        self.assertEqual(field.temporal.name, 'tme')
        self.assertEqual(field.temporal.name_value, 'time')
        self.assertEqual(field.spatial.grid.row.name, 'lat')
        self.assertEqual(field.spatial.grid.row.name_value, 'latitude')
        self.assertEqual(field.spatial.grid.col.name, 'lon')
        self.assertEqual(field.spatial.grid.col.name_value, 'longitude')
        self.assertEqual(field.temporal.name_bounds, 'long_live_the_bounds')

    @attr('data')
    def test_get_field_dtype_on_dimensions(self):
        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        with nc_scope(rd.uri) as ds:
            test_dtype_temporal = ds.variables['time'].dtype
            test_dtype_value = ds.variables['tas'].dtype
        self.assertEqual(field.temporal.dtype, test_dtype_temporal)
        self.assertEqual(field.variables['tas'].dtype, test_dtype_value)
        self.assertEqual(field.temporal.dtype, np.float64)

    @attr('data')
    def test_get_field_dtype_fill_value(self):
        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        # dtype and fill_value should be read from metadata. when accessed they should not load the value.
        self.assertEqual(field.variables['tas'].dtype, np.float32)
        self.assertEqual(field.variables['tas'].fill_value, np.float32(1e20))
        self.assertEqual(field.variables['tas']._value, None)

    @attr('data')
    def test_get_field_datetime_slicing(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri)
        field = rd.get()

        field.temporal.value_datetime
        field.temporal.bounds_datetime

        slced = field[:, 239, :, :, :]
        self.assertEqual(slced.temporal.value_datetime, np.array([dt(2001, 8, 28, 12)]))
        self.assertNumpyAll(slced.temporal.bounds_datetime, np.array([dt(2001, 8, 28), dt(2001, 8, 29)]).reshape(1, 2))

    @attr('data')
    def test_get_field_units_read_from_file(self):
        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        self.assertEqual(field.variables['tas'].cfunits, get_units_object('K'))

    @attr('data')
    def test_get_field_value_datetime_after_slicing(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri)
        field = rd.get()
        slced = field[:, 10:130, :, 4:7, 100:37]
        self.assertEqual(slced.temporal.value_datetime.shape, (120,))

    @attr('data')
    def test_get_field_bounds_datetime_after_slicing(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri)
        field = rd.get()
        slced = field[:, 10:130, :, 4:7, 100:37]
        self.assertEqual(slced.temporal.bounds_datetime.shape, (120, 2))

    @attr('data')
    def test_get_field_slice(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri)
        field = rd.get()
        ds = nc.Dataset(uri, 'r')

        slced = field[:, 56:345, :, :, :]
        self.assertNumpyAll(slced.temporal.value, ds.variables['time'][56:345])
        self.assertNumpyAll(slced.temporal.bounds, ds.variables['time_bnds'][56:345, :])
        to_test = ds.variables['tas'][56:345, :, :]
        to_test = np.ma.array(to_test.reshape(1, 289, 1, 64, 128), mask=False)
        self.assertNumpyAll(slced.variables['tas'].value, to_test)

        slced = field[:, 2898, :, 5, 101]
        to_test = ds.variables['tas'][2898, 5, 101]
        to_test = np.ma.array(to_test.reshape(1, 1, 1, 1, 1), mask=False)
        with self.assertRaises(AttributeError):
            slced.variables['tas']._field._value
        self.assertNumpyAll(slced.variables['tas'].value, to_test)

        ds.close()

    @attr('data')
    def test_get_field_time_range(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri, time_range=[dt(2005, 2, 15), dt(2007, 4, 18)])
        field = rd.get()
        self.assertEqual(field.temporal.value_datetime[0], dt(2005, 2, 15, 12, 0))
        self.assertEqual(field.temporal.value_datetime[-1], dt(2007, 4, 18, 12, 0))
        self.assertEqual(field.shape, (1, 793, 1, 64, 128))

    @attr('data')
    def test_get_field_time_region(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        ds = nc.Dataset(uri, 'r')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri, time_region={'month': [8]})
        field = rd.get()

        self.assertEqual(field.shape, (1, 310, 1, 64, 128))

        var = ds.variables['time']
        real_temporal = nc.num2date(var[:], var.units, var.calendar)
        select = [True if x.month == 8 else False for x in real_temporal]
        indices = np.arange(0, var.shape[0], dtype=np.int32)[np.array(select)]
        self.assertNumpyAll(indices, field.temporal._src_idx)
        self.assertNumpyAll(field.temporal.value_datetime, real_temporal[indices])
        self.assertNumpyAll(field.variables['tas'].value.data.squeeze(), ds.variables['tas'][indices, :, :])

        bounds_temporal = nc.num2date(ds.variables['time_bnds'][indices, :], var.units, var.calendar)
        self.assertNumpyAll(bounds_temporal, field.temporal.bounds_datetime)

        ds.close()

    @attr('data')
    def test_get_field_time_region_with_years(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')
        ds = nc.Dataset(uri, 'r')
        rd = RequestDataset(variable=ref_test['variable'], uri=uri, time_region={'month': [8], 'year': [2008, 2010]})
        field = rd.get()

        self.assertEqual(field.shape, (1, 62, 1, 64, 128))

        var = ds.variables['time']
        real_temporal = nc.num2date(var[:], var.units, var.calendar)
        select = [True if x.month == 8 and x.year in [2008, 2010] else False for x in real_temporal]
        indices = np.arange(0, var.shape[0], dtype=np.int32)[np.array(select)]
        self.assertNumpyAll(indices, field.temporal._src_idx)
        self.assertNumpyAll(field.temporal.value_datetime, real_temporal[indices])
        self.assertNumpyAll(field.variables['tas'].value.data.squeeze(), ds.variables['tas'][indices, :, :])

        bounds_temporal = nc.num2date(ds.variables['time_bnds'][indices, :], var.units, var.calendar)
        self.assertNumpyAll(bounds_temporal, field.temporal.bounds_datetime)

        ds.close()

    @attr('data')
    def test_get_field_geometry_subset(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')

        states = self.get_2d_state_boundaries_sdim()
        ca = states[:, states.properties['STATE_NAME'] == 'California']
        self.assertTrue(ca.properties['STATE_NAME'] == 'California')
        ca.crs.unwrap(ca)
        ca = ca.geom.polygon.value[0, 0]

        for u in [True, False]:
            rd = RequestDataset(variable=ref_test['variable'], uri=uri, alias='foo')
            field = rd.get()
            ca_sub = field.get_intersects(ca, use_spatial_index=u)
            self.assertEqual(ca_sub.shape, (1, 3650, 1, 5, 4))
            self.assertTrue(ca_sub.variables['foo'].value.mask.any())
            self.assertFalse(field.spatial.uid.mask.any())
            self.assertFalse(field.spatial.get_mask().any())

            ca_sub = field.get_intersects(ca.envelope, use_spatial_index=u)
            self.assertEqual(ca_sub.shape, (1, 3650, 1, 5, 4))
            self.assertFalse(ca_sub.variables['foo'].value.mask.any())

            rd = RequestDataset(variable=ref_test['variable'], uri=uri, alias='foo', time_region={'year': [2007]})
            field = rd.get()
            ca_sub = field.get_intersects(ca, use_spatial_index=u)
            self.assertEqual(ca_sub.shape, (1, 365, 1, 5, 4))
            self.assertEqual(set([2007]), set([d.year for d in ca_sub.temporal.value_datetime]))

    @attr('data')
    def test_get_field_time_region_slicing(self):
        ref_test = self.test_data['cancm4_tas']
        uri = self.test_data.get_uri('cancm4_tas')

        rd = RequestDataset(variable=ref_test['variable'], uri=uri, alias='foo',
                            time_region={'month': [1, 10], 'year': [2011, 2013]})
        with self.assertRaises(EmptySubsetError):
            rd.get()

        rd = RequestDataset(variable=ref_test['variable'], uri=uri, alias='foo',
                            time_region={'month': [1, 10], 'year': [2005, 2007]})
        field = rd.get()
        sub = field[:, :, :, 50, 75]
        self.assertEqual(sub.shape, (1, 124, 1, 1, 1))
        self.assertEqual(sub.variables['foo'].value.shape, (1, 124, 1, 1, 1))

        field = rd.get()
        sub = field[:, :, :, 50, 75:77]
        sub2 = field[:, :, :, 0, 1]
        self.assertEqual(sub2.shape, (1, 124, 1, 1, 1))

    @attr('remote', 'slow')
    def test_get_field_remote(self):
        uri = 'http://cida.usgs.gov/thredds/dodsC/maurer/maurer_brekke_w_meta.ncml'
        variable = 'sresa1b_bccr-bcm2-0_1_Tavg'
        rd = RequestDataset(uri, variable, time_region={'month': [1, 10], 'year': [2011, 2013]})
        field = rd.get()
        field.variables['sresa1b_bccr-bcm2-0_1_Tavg'].value
        values = field[:, :, :, 50, 75]
        to_test = values.variables['sresa1b_bccr-bcm2-0_1_Tavg'].value.compressed()

        ds = nc.Dataset('http://cida.usgs.gov/thredds/dodsC/maurer/maurer_brekke_w_meta.ncml', 'r')
        try:
            values = ds.variables['sresa1b_bccr-bcm2-0_1_Tavg'][:, 50, 75]
            times = nc.num2date(ds.variables['time'][:], ds.variables['time'].units, ds.variables['time'].calendar)
            select = np.array([True if time in list(field.temporal.value_datetime) else False for time in times])
            sel_values = values[select]
            self.assertNumpyAll(to_test, sel_values)
        finally:
            ds.close()

    @attr('data')
    def test_get_field_with_projection(self):
        uri = self.test_data.get_uri('narccap_wrfg')
        rd = RequestDataset(uri, 'pr')
        field = rd.get()
        self.assertIsInstance(field.spatial.crs, CFLambertConformal)
        field.spatial.update_crs(CFWGS84())
        self.assertIsInstance(field.spatial.crs, CFWGS84)
        self.assertEqual(field.spatial.grid.row, None)
        self.assertAlmostEqual(field.spatial.grid.value.mean(), -26.269666952512416)
        field.spatial.crs.unwrap(field.spatial)
        self.assertAlmostEqual(field.spatial.grid.value.mean(), 153.73033304748759)
        self.assertIsNone(field.spatial.geom.polygon)
        self.assertAlmostEqual(field.spatial.geom.point.value[0, 100].x, 278.52630062012787)
        self.assertAlmostEqual(field.spatial.geom.point.value[0, 100].y, 21.4615681252577)

    @attr('data')
    def test_get_field_projection_axes(self):
        uri = self.test_data.get_uri('cmip3_extraction')
        variable = 'Tavg'
        rd = RequestDataset(uri, variable)
        with self.assertRaises(DimensionNotFound):
            rd.get()
        rd = RequestDataset(uri, variable, dimension_map={'R': 'projection', 'T': 'time', 'X': 'longitude',
                                                          'Y': 'latitude'})
        field = rd.get()
        self.assertEqual(field.shape, (36, 1800, 1, 7, 12))
        self.assertEqual(field.temporal.value_datetime[0], datetime.datetime(1950, 1, 16, 0, 0))
        self.assertEqual(field.temporal.value_datetime[-1], datetime.datetime(2099, 12, 15, 0, 0))
        self.assertEqual(field.level, None)
        self.assertNumpyAll(field.realization.value, np.arange(1, 37, dtype=np.int32))

        ds = nc.Dataset(uri, 'r')
        to_test = ds.variables['Tavg']
        self.assertNumpyAll(to_test[:], field.variables['Tavg'].value.squeeze())
        ds.close()

    @attr('data')
    def test_get_field_projection_axes_slicing(self):
        uri = self.test_data.get_uri('cmip3_extraction')
        variable = 'Tavg'
        rd = RequestDataset(uri, variable,
                            dimension_map={'R': 'projection', 'T': 'time', 'X': 'longitude', 'Y': 'latitude'})
        field = rd.get()
        sub = field[15, :, :, :, :]
        self.assertEqual(sub.shape, (1, 1800, 1, 7, 12))

        ds = nc.Dataset(uri, 'r')
        to_test = ds.variables['Tavg']
        self.assertNumpyAll(to_test[15, :, :, :], sub.variables[variable].value.squeeze())
        ds.close()

    @attr('data')
    def test_get_field_multifile_load(self):
        uri = self.test_data.get_uri('narccap_pr_wrfg_ncep')
        rd = RequestDataset(uri, 'pr')
        field = rd.get()
        self.assertEqual(field.temporal.extent_datetime,
                         (datetime.datetime(1981, 1, 1, 0, 0), datetime.datetime(1991, 1, 1, 0, 0)))
        self.assertAlmostEqual(field.temporal.resolution, 0.125)

    @attr('data')
    def test_get_field_climatology_bounds(self):
        rd = self.test_data.get_rd('cancm4_tas')
        ops = ocgis.OcgOperations(dataset=rd, output_format='nc', geom='state_boundaries',
                                  select_ugid=[27], calc=[{'func': 'mean', 'name': 'mean'}],
                                  calc_grouping=['month'])
        ret = ops.execute()
        rd = RequestDataset(uri=ret, variable='mean')
        field = rd.get()
        self.assertIsNotNone(field.temporal.bounds)

    def test_get_field_without_row_column_vectors(self):
        """Test loading a field object without row and column vectors."""

        path = self.get_netcdf_path_no_row_column()

        rd = RequestDataset(path)
        driver = DriverNetcdf(rd)
        new_field = driver.get_field()
        self.assertIsNotNone(new_field.crs)
        grid = new_field.spatial.grid
        self.assertIsNone(grid.row)
        self.assertIsNone(grid.col)
        self.assertEqual(grid.name_row, 'yc')
        self.assertEqual(grid.name_col, 'xc')
        self.assertIsNone(grid._value)
        actual = np.ma.array([[[4.0, 4.0], [5.0, 5.0]], [[40.0, 50.0], [40.0, 50.0]]])
        self.assertNumpyAll(grid.value, actual)
        var = new_field.variables.first()
        self.assertEqual(var.shape, (1, 2, 1, 2, 2))
        self.assertEqual(var.value.shape, (1, 2, 1, 2, 2))

        new_field = driver.get_field()
        grid = new_field.spatial.grid
        self.assertEqual(grid.shape, (2, 2))
        self.assertIsNone(grid._value)
        sub = new_field[:, :, :, 0, 1]
        sub_grid = sub.spatial.grid
        self.assertIsInstance(sub_grid, NcSpatialGridDimension)
        self.assertEqual(sub.shape, (1, 2, 1, 1, 1))
        self.assertIsNone(sub_grid._value)
        self.assertEqual(sub_grid.shape, (1, 1))
        actual = np.ma.array([[[4.0]], [[50.0]]])
        self.assertNumpyAll(actual, sub_grid.value)
        sub_var = sub.variables.first()
        self.assertEqual(sub_var.shape, (1, 2, 1, 1, 1))
        self.assertEqual(sub_var.value.shape, (1, 2, 1, 1, 1))

        path2 = os.path.join(self.current_dir_output, 'foo2.nc')
        with self.nc_scope(path2, 'w') as ds:
            new_field.write_netcdf(ds)
        self.assertNcEqual(path, path2, ignore_attributes={'foo': ['grid_mapping']},
                           ignore_variables=['latitude_longitude'])

    @attr('data')
    def test_get_name_bounds_dimension(self):
        rd = self.test_data.get_rd('cancm4_tas')
        source_metadata = rd.source_metadata
        res = DriverNetcdf._get_name_bounds_dimension_(source_metadata)
        self.assertEqual(res, 'bnds')

        # remove any mention of bounds from the dimension map and try again
        for value in source_metadata['dim_map'].itervalues():
            try:
                value['bounds'] = None
            except TypeError:
                # likely a nonetype
                if value is not None:
                    raise
        res = DriverNetcdf._get_name_bounds_dimension_(source_metadata)
        self.assertIsNone(res)

        # now remove the bounds key completely
        for value in source_metadata['dim_map'].itervalues():
            try:
                value.pop('bounds')
            except AttributeError:
                if value is not None:
                    raise
        res = DriverNetcdf._get_name_bounds_dimension_(source_metadata)
        self.assertIsNone(res)

    @attr('data')
    def test_get_source_metadata(self):
        dimension_map = {'X': {'variable': 'lon', 'dimension': 'x', 'pos': 2, 'bounds': 'lon_bnds'},
                         'Y': {'variable': 'lat', 'dimension': 'y', 'pos': 1, 'bounds': 'lat_bounds'},
                         'T': {'variable': 'time', 'dimension': 'time', 'pos': 0, 'bounds': 'time_bounds'}}
        uri = self.test_data.get_uri('cancm4_tas')
        rd = RequestDataset(uri=uri, dimension_map=dimension_map)
        driver = DriverNetcdf(rd)
        meta = driver.get_source_metadata()
        self.assertEqual(meta['dim_map'], dimension_map)

        # test with no dimensioned variables
        uri = self.get_netcdf_path_no_dimensioned_variables()
        rd = RequestDataset(uri=uri)
        driver = DriverNetcdf(rd)
        meta = driver.get_source_metadata()
        self.assertEqual(meta['dimensions']['dim']['len'], 0)
        with self.assertRaises(KeyError):
            meta['dim_map']

    @attr('data')
    def test_source_metadata_as_json(self):
        rd = self.test_data.get_rd('cancm4_tas')
        driver = DriverNetcdf(rd)
        js = driver.get_source_metadata_as_json()
        self.assertIsInstance(js, basestring)
        self.assertTrue(len(js) > 100)

    def test_get_vector_dimension(self):
        # test exception raised with no row and column
        path = self.get_netcdf_path_no_row_column()
        rd = RequestDataset(path)
        driver = DriverNetcdf(rd)
        k = 'row'
        v = {'name_uid': 'yc_id', 'axis': 'Y', 'adds': {'interpolate_bounds': False}, 'name': 'yc',
             'cls': VectorDimension}
        source_metadata = rd.source_metadata
        res = driver._get_vector_dimension_(k, v, source_metadata)
        self.assertEqual(res['name'], 'yc')

    # @attr('data')
    # def test_inspect(self):
    #     rd = self.test_data.get_rd('cancm4_tas')
    #     driver = DriverNetcdf(rd)
    #     with self.print_scope() as ps:
    #         driver.inspect()
    #     self.assertTrue(len(ps.storage) >= 1)
    #
    #     # test with a request dataset having no dimensioned variables
    #     path = self.get_temporary_file_path('bad.nc')
    #     with self.nc_scope(path, 'w') as ds:
    #         ds.createDimension('foo')
    #         var = ds.createVariable('foovar', int, dimensions=('foo',))
    #         var.a_name = 'a name'
    #     rd = RequestDataset(uri=path)
    #     driver = DriverNetcdf(rd)
    #     with self.print_scope() as ps:
    #         driver.inspect()
    #     self.assertTrue(len(ps.storage) >= 1)

    @attr('data')
    def test_open(self):
        # test a multifile dataset where the variable does not appear in all datasets
        uri1 = self.test_data.get_uri('cancm4_tas')
        uri2 = self.test_data.get_uri('cancm4_tasmax_2001')
        uri = [uri1, uri2]
        rd = RequestDataset(uri=uri, variable='tas')
        driver = DriverNetcdf(rd)
        with self.assertRaises(KeyError):
            driver.open()
        with self.assertRaises(KeyError):
            rd.source_metadata


class Test(TestBase):
    def setUp(self):
        raise SkipTest('outdated dimension map tests')

    @attr('data')
    def test_get_dimension_map_1(self):
        """Test dimension dictionary returned correctly."""

        rd = self.test_data.get_rd('cancm4_tas')
        dim_map = get_dimension_map('tas', rd.source_metadata)
        self.assertDictEqual(dim_map, {'Y': {'variable': u'lat', 'bounds': u'lat_bnds', 'dimension': u'lat', 'pos': 1},
                                       'X': {'variable': u'lon', 'bounds': u'lon_bnds', 'dimension': u'lon', 'pos': 2},
                                       'Z': None,
                                       'T': {'variable': u'time', 'bounds': u'time_bnds', 'dimension': u'time',
                                             'pos': 0}})

    def test_get_dimension_map_2(self):
        """Test special case where bounds were in the file but not found by the code."""

        # this metadata was causing an issue with the bounds not being discovered (Maurer02new_OBS_tas_daily.1971-2000.nc)
        # rd = RequestDataset(uri='/usr/local/climate_data/maurer/2010-concatenated/Maurer02new_OBS_tas_daily.1971-2000.nc', variable='tas')
        # metadata = rd.source_metadata
        metadata = NcMetadata([('dataset', OrderedDict(
            [(u'CDI', u'Climate Data Interface version 1.5.0 (http://code.zmaw.de/projects/cdi)'),
             (u'Conventions', u'GDT 1.2'), (u'history',
                                            u'Wed Jul  3 07:17:09 2013: ncrcat nldas_met_update.obs.daily.tas.1971.nc nldas_met_update.obs.daily.tas.1972.nc nldas_met_update.obs.daily.tas.1973.nc nldas_met_update.obs.daily.tas.1974.nc nldas_met_update.obs.daily.tas.1975.nc nldas_met_update.obs.daily.tas.1976.nc nldas_met_update.obs.daily.tas.1977.nc nldas_met_update.obs.daily.tas.1978.nc nldas_met_update.obs.daily.tas.1979.nc nldas_met_update.obs.daily.tas.1980.nc nldas_met_update.obs.daily.tas.1981.nc nldas_met_update.obs.daily.tas.1982.nc nldas_met_update.obs.daily.tas.1983.nc nldas_met_update.obs.daily.tas.1984.nc nldas_met_update.obs.daily.tas.1985.nc nldas_met_update.obs.daily.tas.1986.nc nldas_met_update.obs.daily.tas.1987.nc nldas_met_update.obs.daily.tas.1988.nc nldas_met_update.obs.daily.tas.1989.nc nldas_met_update.obs.daily.tas.1990.nc nldas_met_update.obs.daily.tas.1991.nc nldas_met_update.obs.daily.tas.1992.nc nldas_met_update.obs.daily.tas.1993.nc nldas_met_update.obs.daily.tas.1994.nc nldas_met_update.obs.daily.tas.1995.nc nldas_met_update.obs.daily.tas.1996.nc nldas_met_update.obs.daily.tas.1997.nc nldas_met_update.obs.daily.tas.1998.nc nldas_met_update.obs.daily.tas.1999.nc nldas_met_update.obs.daily.tas.2000.nc Maurer02new_OBS_tas_daily.1971-2000.nc\nFri Oct 28 08:44:48 2011: cdo ifthen conus_mask.nc /archive/public/gridded_obs/daily/ncfiles_2010/nldas_met_update.obs.daily.tas.1971.nc /data3/emaurer/ldas_met_2010/process/met/nc/daily/nldas_met_update.obs.daily.tas.1971.nc'),
             (u'institution', u'Princeton U.'), (u'file_name', u'nldas_met_update.obs.daily.tas.1971.nc'),
             (u'History', u'Interpolated from 1-degree data'), (u'authors',
                                                                u'Sheffield, J., G. Goteti, and E. F. Wood, 2006: Development of a 50-yr high-resolution global dataset of meteorological forcings for land surface modeling, J. Climate, 19 (13), 3088-3111'),
             (u'description', u'Gridded Observed global data'), (u'creation_date', u'2006'),
             (u'SurfSgnConvention', u'Traditional'),
             (u'CDO', u'Climate Data Operators version 1.5.0 (http://code.zmaw.de/projects/cdo)'),
             (u'nco_openmp_thread_number', 1)])), ('file_format', 'NETCDF3_CLASSIC'), ('variables', OrderedDict([(
                                                                                                                     u'longitude',
                                                                                                                     {
                                                                                                                         'dtype': 'float32',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'longitude',),
                                                                                                                         'name': u'longitude',
                                                                                                                         'attrs': OrderedDict(
                                                                                                                             [
                                                                                                                                 (
                                                                                                                                     u'long_name',
                                                                                                                                     u'Longitude'),
                                                                                                                                 (
                                                                                                                                     u'units',
                                                                                                                                     u'degrees_east'),
                                                                                                                                 (
                                                                                                                                     u'standard_name',
                                                                                                                                     u'longitude'),
                                                                                                                                 (
                                                                                                                                     u'axis',
                                                                                                                                     u'X'),
                                                                                                                                 (
                                                                                                                                     u'bounds',
                                                                                                                                     u'longitude_bnds')])}),
                                                                                                                 (
                                                                                                                     u'longitude_bnds',
                                                                                                                     {
                                                                                                                         'dtype': 'float32',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'longitude',
                                                                                                                             u'nb2'),
                                                                                                                         'name': u'longitude_bnds',
                                                                                                                         'attrs': OrderedDict()}),
                                                                                                                 (
                                                                                                                     u'latitude',
                                                                                                                     {
                                                                                                                         'dtype': 'float32',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'latitude',),
                                                                                                                         'name': u'latitude',
                                                                                                                         'attrs': OrderedDict(
                                                                                                                             [
                                                                                                                                 (
                                                                                                                                     u'long_name',
                                                                                                                                     u'Latitude'),
                                                                                                                                 (
                                                                                                                                     u'units',
                                                                                                                                     u'degrees_north'),
                                                                                                                                 (
                                                                                                                                     u'standard_name',
                                                                                                                                     u'latitude'),
                                                                                                                                 (
                                                                                                                                     u'axis',
                                                                                                                                     u'Y'),
                                                                                                                                 (
                                                                                                                                     u'bounds',
                                                                                                                                     u'latitude_bnds')])}),
                                                                                                                 (
                                                                                                                     u'latitude_bnds',
                                                                                                                     {
                                                                                                                         'dtype': 'float32',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'latitude',
                                                                                                                             u'nb2'),
                                                                                                                         'name': u'latitude_bnds',
                                                                                                                         'attrs': OrderedDict()}),
                                                                                                                 (
                                                                                                                     u'time',
                                                                                                                     {
                                                                                                                         'dtype': 'float64',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'time',),
                                                                                                                         'name': u'time',
                                                                                                                         'attrs': OrderedDict(
                                                                                                                             [
                                                                                                                                 (
                                                                                                                                     u'units',
                                                                                                                                     u'days since 1940-01-01 00:00:00'),
                                                                                                                                 (
                                                                                                                                     u'calendar',
                                                                                                                                     u'standard')])}),
                                                                                                                 (
                                                                                                                     u'tas',
                                                                                                                     {
                                                                                                                         'dtype': 'float32',
                                                                                                                         'fill_value': 1e+20,
                                                                                                                         'dimensions': (
                                                                                                                             u'time',
                                                                                                                             u'latitude',
                                                                                                                             u'longitude'),
                                                                                                                         'name': u'tas',
                                                                                                                         'attrs': OrderedDict(
                                                                                                                             [
                                                                                                                                 (
                                                                                                                                     u'units',
                                                                                                                                     u'C')])})])),
                               ('dimensions', OrderedDict([(u'longitude', {'isunlimited': False, 'len': 462}),
                                                           (u'nb2', {'isunlimited': False, 'len': 2}),
                                                           (u'latitude', {'isunlimited': False, 'len': 222}),
                                                           (u'time', {'isunlimited': True, 'len': 10958})]))])
        dim_map = get_dimension_map('tas', metadata)
        self.assertDictEqual(dim_map, {
            'Y': {'variable': u'latitude', 'bounds': u'latitude_bnds', 'dimension': u'latitude', 'pos': 1},
            'X': {'variable': u'longitude', 'bounds': u'longitude_bnds', 'dimension': u'longitude', 'pos': 2},
            'Z': None,
            'T': {'variable': u'time', 'bounds': None, 'dimension': u'time', 'pos': 0}})

    @attr('data')
    def test_get_dimension_map_3(self):
        """Test when bounds are found but the bounds variable is actually missing."""

        # remove the bounds variable from a standard metadata dictionary
        def _run_():
            env.SUPPRESS_WARNINGS = False
            rd = self.test_data.get_rd('cancm4_tas')
            metadata = deepcopy(rd.source_metadata)
            metadata['variables'].pop('lat_bnds')
            dim_map = get_dimension_map('tas', metadata)
            self.assertEqual(dim_map['Y']['bounds'], None)

        self.assertWarns(OcgWarning, _run_)
