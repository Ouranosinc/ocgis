from copy import deepcopy

from ocgis import OcgOperations
from ocgis.driver.base import AbstractDriver
from ocgis.driver.nc import DriverNetcdf
from ocgis.exc import DefinitionValidationError
from ocgis.test.base import TestBase
from ocgis.test.base import attr
from ocgis.variable.crs import WGS84


class FakeAbstractDriver(AbstractDriver):
    output_formats = ['shp']
    key = 'fake_driver'

    def _get_field_(self, **kwargs):
        pass

    def get_crs(self):
        pass

    def get_source_metadata(self):
        pass

    def extensions(self):
        pass

    def open(self):
        pass

    def get_data_variable_names(self):
        pass

    def close(self, obj):
        pass


class TestAbstractDriver(TestBase):
    @attr('data')
    def test_get_field(self):
        # test updating of regrid source flag
        rd = self.test_data.get_rd('cancm4_tas')
        driver = DriverNetcdf(rd)
        field = driver.get_field()
        self.assertTrue(field.regrid_source)
        rd.regrid_source = False
        driver = DriverNetcdf(rd)
        field = driver.get_field()
        self.assertFalse(field.regrid_source)

        # test flag with an assigned coordinate system
        rd = self.test_data.get_rd('cancm4_tas')
        driver = DriverNetcdf(rd)
        field = driver.get_field()
        self.assertFalse(field._has_assigned_coordinate_system)

        rd = self.test_data.get_rd('cancm4_tas', kwds={'crs': WGS84()})
        self.assertTrue(rd._has_assigned_coordinate_system)
        driver = DriverNetcdf(rd)
        field = driver.get_field()
        self.assertTrue(field._has_assigned_coordinate_system)

    @attr('data')
    def test_eq(self):
        rd = self.test_data.get_rd('cancm4_tas')
        d = DriverNetcdf(rd)
        d2 = deepcopy(d)
        self.assertEqual(d, deepcopy(d))

        d2.key = 'bad'
        self.assertNotEqual(d, d2)

    @attr('data')
    def test_inspect(self):
        rd = self.test_data.get_rd('cancm4_tas')
        driver = DriverNetcdf(rd)
        with self.print_scope() as ps:
            driver.inspect()
        self.assertTrue(len(ps.storage) > 1)

    @attr('data')
    def test_validate_ops(self):
        rd = self.test_data.get_rd('cancm4_tas')
        ops = OcgOperations(dataset=rd)

        with self.assertRaises(DefinitionValidationError):
            FakeAbstractDriver.validate_ops(ops)

        prev = FakeAbstractDriver.output_formats
        FakeAbstractDriver.output_formats = 'all'
        try:
            FakeAbstractDriver.validate_ops(ops)
        finally:
            FakeAbstractDriver.output_formats = prev
