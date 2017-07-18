import itertools
import os
import re
import shutil
import tempfile
from zipfile import is_zipfile, ZipFile

import ocgis
from ocgis import constants
from ocgis.test.base import TestBase, attr
from ocgis.util.zipper import format_return


class Test(TestBase):
    @attr('data')
    def test(self):
        tdata = TestBase.get_tst_data()
        rd = tdata.get_rd('cancm4_tas')

        output_formats = [constants.OutputFormatName.CSV_SHAPEFILE,
                          constants.OutputFormatName.CSV,
                          constants.OutputFormatName.NETCDF,
                          constants.OutputFormatName.SHAPEFILE,
                          constants.OutputFormatName.OCGIS]
        _with_auxiliary_files = [True, False]
        for output_format, with_auxiliary_files in itertools.product(output_formats, _with_auxiliary_files):
            dir_output = tempfile.mkdtemp()
            try:
                ocgis.env.DIR_OUTPUT = dir_output

                ops = ocgis.OcgOperations(dataset=rd, snippet=True, output_format=output_format,
                                          geom='state_boundaries',
                                          select_ugid=[23], prefix=output_format + '_data')
                ret_path = ops.execute()

                fmtd_ret = format_return(ret_path, ops, with_auxiliary_files=with_auxiliary_files)

                assert (os.path.exists(fmtd_ret))
                if output_format in [constants.OutputFormatName.CSV,
                                     constants.OutputFormatName.NETCDF] and with_auxiliary_files is False:
                    assert (fmtd_ret.endswith(output_format))
                else:
                    assert (is_zipfile(fmtd_ret))
                    zipf = ZipFile(fmtd_ret, 'r')
                    try:
                        namelist = zipf.namelist()
                        assert (len(namelist) > 0)
                        if output_format in [constants.OutputFormatName.CSV_SHAPEFILE]:
                            test = [re.match('shp/.+'.format(output_format), name) != None for name in namelist]
                            assert (any(test))
                        else:
                            test = [re.match('shp/.+'.format(output_format), name) == None for name in namelist]
                            assert (all(test))
                    finally:
                        zipf.close()
            # numpy formats are not implemented
            except NotImplementedError:
                assert (output_format == constants.OutputFormatName.OCGIS)
            finally:
                ocgis.env.reset()
                shutil.rmtree(dir_output)
