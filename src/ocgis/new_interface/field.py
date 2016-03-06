from collections import OrderedDict
from copy import deepcopy

from ocgis.interface.base.crs import CoordinateReferenceSystem
from ocgis.new_interface.base import renamed_dimensions_on_variables
from ocgis.new_interface.grid import GridXY
from ocgis.new_interface.temporal import TemporalVariable
from ocgis.new_interface.variable import VariableCollection

# tdk: move this to ocgis.constants
_DIMENSION_MAP = OrderedDict()
_DIMENSION_MAP['realization'] = {'attrs': {'axis': 'R'}, 'variable': None, 'names': []}
_DIMENSION_MAP['time'] = {'attrs': {'axis': 'T'}, 'variable': None, 'bounds': None, 'names': []}
_DIMENSION_MAP['level'] = {'attrs': {'axis': 'L'}, 'variable': None, 'bounds': None, 'names': []}
_DIMENSION_MAP['y'] = {'attrs': {'axis': 'Y'}, 'variable': None, 'bounds': None, 'names': []}
_DIMENSION_MAP['x'] = {'attrs': {'axis': 'X'}, 'variable': None, 'bounds': None, 'names': []}
_DIMENSION_MAP['geom'] = {'attrs': {'axis': 'ocgis_geom'}, 'variable': None, 'names': []}
_DIMENSION_MAP['crs'] = {'attrs': None, 'variable': None, 'names': []}


class OcgField(VariableCollection):

    def __init__(self, *args, **kwargs):
        dimension_map = deepcopy(kwargs.pop('dimension_map', None))
        dimension_map_template = deepcopy(_DIMENSION_MAP)
        if dimension_map is not None:
            for k, v in dimension_map.items():
                for k2, v2, in v.items():
                    if k2 == 'attrs':
                        dimension_map_template[k][k2].update(v2)
                    else:
                        dimension_map_template[k][k2] = v2
        self.dimension_map = dimension_map_template

        self.grid_abstraction = kwargs.pop('grid_abstraction', 'auto')
        self.format_tine = kwargs.pop('format_time', True)

        VariableCollection.__init__(self, *args, **kwargs)

    def __getitem__(self, item):
        if not isinstance(item, basestring):
            name_mapping = {}
            for k, v in self.dimension_map.items():
                variable_name = v['variable']
                if variable_name is not None:
                    dimension_name = self[variable_name].dimensions[0].name
                    variable_names = v['names']
                    if dimension_name not in variable_names:
                        variable_names.append(dimension_name)
                    name_mapping[k] = variable_names
            with renamed_dimensions_on_variables(self, name_mapping):
                ret = super(OcgField, self).__getitem__(item)
        else:
            ret = super(OcgField, self).__getitem__(item)
        return ret

    @property
    def crs(self):
        return get_field_property(self, 'crs')

    @property
    def realization(self):
        return get_field_property(self, 'realization')

    @property
    def time(self):
        ret = get_field_property(self, 'time')
        ret = TemporalVariable.from_variable(ret, format_time=self.format_tine)
        return ret

    @property
    def level(self):
        return get_field_property(self, 'level')

    @property
    def y(self):
        return get_field_property(self, 'y')

    @property
    def x(self):
        return get_field_property(self, 'x')

    @property
    def grid(self):
        # tdk: test abstraction
        x = self.x
        y = self.y
        if x is None or y is None:
            ret = None
        else:
            ret = GridXY(self.x, self.y, parent=self, crs=self.crs, abstraction=self.grid_abstraction)
        return ret

    @property
    def geom(self):
        ret = get_field_property(self, 'geom')
        if ret is not None:
            crs = self.crs
            # Overload the geometry coordinate system if set on the field. Otherwise, this will (obviously) use the
            # coordinate system on the geometry variable.
            if crs is not None:
                ret.crs = crs
        else:
            # Attempt to pull the geometry from the grid.
            grid = self.grid
            if grid is not None:
                ret = grid.abstraction_geometry
        return ret

    def write_netcdf(self, dataset_or_path, **kwargs):
        # Attempt to load all instrumented dimensions once. Do not do this for the geometry variable.
        for k in self.dimension_map.keys():
            if k != 'geom':
                getattr(self, k)
        return super(OcgField, self).write_netcdf(dataset_or_path, **kwargs)


def get_field_property(field, name):
    variable = field.dimension_map[name]['variable']
    bounds = field.dimension_map[name].get('bounds')
    if variable is None:
        ret = None
    else:
        ret = field[variable]
        if not isinstance(ret, CoordinateReferenceSystem):
            ret.attrs.update(field.dimension_map[name]['attrs'])
            if bounds is not None:
                ret.bounds = field[bounds]
    return ret
