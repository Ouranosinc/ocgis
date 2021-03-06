import os

from setuptools import setup, Command, find_packages
from setuptools.command.test import test as TestCommand

VERSION = '2.0.0'


########################################################################################################################
# commands
########################################################################################################################


class TestCommandOcgis(TestCommand):
    user_options = [('with-optional', None, 'If present, run optional dependency tests.')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.with_optional = False
        self.no_esmf = False
        self.no_icclim = False

    # def finalize_options(self):
    #     pass

    def run_tests(self):
        from ocgis.test import run_simple

        attrs = ['simple']
        if self.with_optional:
            to_append = 'optional'
            attrs.append(to_append)

        run_simple(attrs=attrs, verbose=False)


class TestMoreCommandOcgis(TestCommand):
    description = 'run most tests (exludes data, slow, remote, benchmark, etc.)'

    def run_tests(self):
        from ocgis.test import run_more

        run_more(verbose=False)


class TestAllCommandOcgis(TestCommand):
    description = 'run all tests except benchmark tests'

    def run_tests(self):
        from ocgis.test import run_all

        run_all(verbose=False)


class UninstallCommand(Command):
    description = "information on how to uninstall OCGIS"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            import ocgis

            print('To uninstall, manually remove the Python package folder located here: {0}'.format(
                os.path.split(ocgis.__file__)[0]))
        except ImportError:
            raise ImportError("Either OpenClimateGIS is not installed or not available on the Python path.")

########################################################################################################################
# set up data files for installation
########################################################################################################################

shp_parts = ['state_boundaries.cfg', 'state_boundaries.dbf', 'state_boundaries.prj', 'state_boundaries.shp',
             'state_boundaries.shx']
shp_parts = ['bin/shp/state_boundaries/{0}'.format(element) for element in shp_parts]
bin_files = ['bin/test_csv_calc_conversion_two_calculations.csv']
bin_files += shp_parts
package_data = {'ocgis.test': bin_files}

########################################################################################################################
# setup command
########################################################################################################################

setup(
    name='ocgis',
    version=VERSION,
    author='NESII/CIRES/NOAA-ESRL',
    author_email='ocgis_support@list.woc.noaa.gov',
    url='http://ocgis.readthedocs.io/en/latest/install.html',
    license='NCSA License',
    platforms=['all'],
    packages=find_packages(where='./src'),
    package_dir={'': 'src'},
    package_data=package_data,
    cmdclass={'uninstall': UninstallCommand,
              'test': TestCommandOcgis,
              'test_more': TestMoreCommandOcgis,
              'test_all': TestAllCommandOcgis},
    install_requires=['numpy', 'netCDF4', 'fiona', 'shapely', 'pyproj', 'six', 'gdal'],
    tests_require=['nose']
)
