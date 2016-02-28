from collections import OrderedDict
from copy import deepcopy

from ocgis.interface.base.crs import CoordinateReferenceSystem
from ocgis.new_interface.base import renamed_dimensions_on_variables
from ocgis.new_interface.grid import GridXY
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
        self.dimension_map = kwargs.pop('dimension_map', deepcopy(_DIMENSION_MAP))
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
        return get_field_property(self, 'time')

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
        # Attempt to load all instrumented dimensions once.
        for k in self.dimension_map.keys():
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

# class FieldBundle2(AbstractOperationsSpatialObject):
#     """
#     :type fields: sequence of variable aliases
#
#     >>> fields = ['tas', 'pr']
#     """
#
#     def __init__(self, **kwargs):
#         self._variables = None
#         self._fields = None
#         self._spatial = None
#         self._abstraction = None
#
#         self.dimension_map = deepcopy(_DIMENSION_MAP)
#
#         self.fields = kwargs.pop('fields', None)
#         self.variables = kwargs.pop('variables', None)
#         spatial = kwargs.pop('spatial', None)
#
#         super(FieldBundle2, self).__init__(**kwargs)
#
#         # Allow spatial container to override "crs".
#         self.spatial = spatial
#
#     def __getitem__(self, slc):
#         if isinstance(slc, basestring):
#             ret = super(FieldBundle2, self).__getitem__(slc)
#         else:
#             target = self.variables.first()
#             slc = get_formatted_slice(slc, target.ndim)
#             backref = self.variables.copy()
#             backref.pop(target.name)
#             target._backref = backref
#             sub = target.__getitem__(slc)
#             ret = self.copy()
#             new_variables = sub._backref
#             sub._backref = None
#             new_variables.add_variable(sub)
#             ret.variables.update(new_variables)
#             for field in ret.fields.values():
#                 ret.fields[field.name] = new_variables[field.name]
#         return ret
#
#     def __getattribute__(self, name_or_slice):
#         _getattr = object.__getattribute__
#         try:
#             ret = _getattr(self, name_or_slice)
#         except AttributeError as e:
#             try:
#                 desired_dimension = _getattr(self, 'dimension_map')[name_or_slice]
#             except (KeyError, AttributeError):
#                 raise e
#             else:
#                 desired_dimension_variable = desired_dimension['variable']
#                 ret = _getattr(self, 'variables').get(desired_dimension_variable, None)
#         return ret
#
#     @property
#     def dimensions(self):
#         return self.fields.first().dimensions
#
#     @property
#     def dimensions_dict(self):
#         return self.fields.first().dimensions_dict
#
#     @property
#     def fields(self):
#         return self._fields
#
#     @fields.setter
#     def fields(self, fields):
#         self._fields = VariableCollection(variables=fields)
#
#     @property
#     def variables(self):
#         ret = self._variables
#         ret.update(self.fields)
#         self.update_mapped_dimensions()
#         return ret
#
#     @variables.setter
#     def variables(self, variables):
#         self._variables = VariableCollection(variables=variables)
#
#     @property
#     def spatial(self):
#         kwds = {}
#         kwds['abstraction'] = self._abstraction
#
#         try:
#             grid = GridXY(self.x, self.y, crs=self.crs)
#         except AttributeError:  # Assume x or y is None.
#             pass
#         else:
#             kwds['grid'] = grid
#
#         try:
#             geom = self.geom
#             archetype = geom.value.flatten()[0]
#         except AttributeError:  # Assume no geometry.
#             pass
#         else:
#             if archetype.geom_type in ['Point', 'MultiPoint']:
#                 kwds['point'] = geom
#             elif archetype.geom_type in ['Polygon', 'MultiPolygon']:
#                 kwds['polygon'] = geom
#         return SpatialContainer(**kwds)
#
#     @spatial.setter
#     def spatial(self, value):
#         if value is not None:
#             self.variables.update(value.as_variable_collection())
#             self.crs = value.crs
#             self._abstraction = value.abstraction
#
#     def get_intersects(self, *args, **kwargs):
#         raise NotImplementedError
#
#     def get_subset_bbox(self, *args, **kwargs):
#         raise NotImplementedError
#
#     def update_crs(self, to_crs):
#         raise NotImplementedError
#
#     def update_mapped_dimensions(self):
#         for name, v in self.dimension_map.items():
#             name_variable = v['variable']
#             try:
#                 self.set_dimension_variable(name, name_variable)
#             except KeyError:  # Assume not in variables.
#                 pass
#
#     def set_dimension_variable(self, name, name_variable):
#         self.dimension_map[name]['variable'] = name_variable
#         desired_variable = self._variables[name_variable]
#         desired_dimension = desired_variable.dimensions[0]
#         for var in self._variables.values():
#             if var.dimensions is not None:
#                 new_dimensions = list(var.dimensions)
#                 try:
#                     idx = [d.name for d in var.dimensions].index(desired_dimension.name)
#                 except ValueError:  # Assume dimension not in list.
#                     continue
#                 new_dimensions[idx] = desired_dimension
#                 var.dimensions_dict[desired_dimension.name].attach_variable(desired_variable)
#
#     def write_netcdf(self, *args, **kwargs):
#         if self.crs is not None:
#             var_crs = self.crs.as_variable()
#             self.variables.add_variable(var_crs)
#
#         for name in self.dimension_map.keys():
#             mapped_dimension = getattr(self, name)
#             if mapped_dimension is not None:
#                 mapped_dimension.attrs.update(deepcopy(self.dimension_map[name]['attrs']))
#
#         VariableCollection.write_netcdf(self.variables, *args, **kwargs)
#
#     def _get_extent_(self):
#         raise NotImplementedError

# class FieldBundle(AbstractInterfaceObject, Attributes):
#     def __init__(self, **kwargs):
#         self._should_sync = False
#         self._realization = None
#         self._time = None
#         self._level = None
#         self._spatial = None
#
#         self.inherit_names = kwargs.pop('inherit_names', True)
#         self.name = kwargs.pop('name')
#         self.fields = kwargs.pop('fields', VariableCollection())
#         self.realization = kwargs.pop('realization', None)
#         self.time = kwargs.pop('time', None)
#         # Backwards compatibility.
#         if self._time is None:
#             self.temporal = kwargs.pop('temporal', None)
#         self._dimension_schema = deepcopy(_FIELDBUNDLE_DIMENSION_NAMES)
#
#         self.level = kwargs.pop('level', None)
#         self.spatial = kwargs.pop('spatial', None)
#         self.extra = kwargs.pop('extra', VariableCollection())
#         self.schemas = kwargs.pop('schemas', OrderedDict())
#
#         Attributes.__init__(self, **kwargs)
#
#         self.should_sync = True
#
#     def __getitem__(self, slc):
#         slc = get_formatted_slice(slc, self.ndim)
#         ret = copy(self)
#         ret.should_sync = False
#         ret.fields = VariableCollection()
#         for alias, f in self.fields.items():
#             ret.fields.add_variable(f[slc])
#         slc_fb = {}
#         fb_dimensions = []
#         for ii in self._dimension_schema.values():
#             fb_dimensions += ii
#         for idx, d in enumerate(self.dimensions):
#             if d.name in fb_dimensions:
#                 slc_fb[d.name] = slc[idx]
#         set_getitem_field_bundle(ret, slc_fb)
#         ret.should_sync = True
#         return ret
#
#     @property
#     def dimensions(self):
#         var = self.fields.first()
#         if var is None:
#             ret = None
#         else:
#             ret = var.dimensions
#         return ret
#
#     @property
#     def ndim(self):
#         return len(self.dimensions)
#
#     @property
#     def realization(self):
#         return self._realization
#
#     @realization.setter
#     def realization(self, value):
#         self._set_dimension_variable_('_realization', value, 'R')
#
#     @property
#     def shape(self):
#         dimensions = self.dimensions
#         if dimensions is None:
#             ret = None
#         else:
#             ret = tuple([d.length for d in self.dimensions])
#         return ret
#
#     @property
#     def should_sync(self):
#         return self._should_sync
#
#     @should_sync.setter
#     def should_sync(self, value):
#         self._should_sync = value
#         if value:
#             self.sync()
#
#     @property
#     def temporal(self):
#         return self._time
#
#     @temporal.setter
#     def temporal(self, value):
#         self._set_time_(value)
#
#     @property
#     def time(self):
#         return self._time
#
#     @time.setter
#     def time(self, value):
#         self._set_time_(value)
#
#     def _set_time_(self, value):
#         if value is not None:
#             assert isinstance(value, TemporalVariable)
#         self._set_dimension_variable_('_time', value, 'T')
#
#     @property
#     def level(self):
#         return self._level
#
#     @level.setter
#     def level(self, value):
#         self._set_dimension_variable_('_level', value, 'L')
#
#     @property
#     def spatial(self):
#         return self._spatial
#
#     @spatial.setter
#     def spatial(self, value):
#         if value is not None:
#             assert isinstance(value, SpatialContainer)
#             value = value.copy()
#         self._spatial = value
#         self.sync()
#
#     def copy(self):
#         return copy(self)
#
#     def create_field(self, variable, schema=None, rename_dimensions=False):
#         self.should_sync = False
#         if schema is not None:
#             for k, v in schema.items():
#                 if rename_dimensions:
#                     for idx, d in enumerate(variable.dimensions):
#                         if d.name == v:
#                             variable.dimensions[idx].name = k
#                             break
#                 else:
#                     if v not in self._dimension_schema[k]:
#                         self._dimension_schema[k].append(v)
#         variable.attrs = variable.attrs.copy()
#         self.schemas[variable.alias] = schema
#         self.fields[variable.alias] = variable
#         self.should_sync = True
#
#     def sync(self):
#         if self.should_sync:
#             crs = self.crs
#             for f in self.fields.itervalues():
#                 if crs is not None:
#                     attrs = f.attrs
#                     crs_name = crs.name
#                     if 'grid_mapping_name' not in attrs:
#                         attrs['grid_mapping_name'] = crs_name
#
#             if self.inherit_names:
#                 # Update grid dimension names.
#                 if self.spatial is not None:
#                     try:
#                         name_y = self._dimension_schema['y'][1]
#                         name_x = self._dimension_schema['x'][1]
#                     except IndexError:
#                         # No new dimension names for x and y.
#                         pass
#                     else:
#                         self.spatial.grid.name_y = name_y
#                         self.spatial.grid.name_x = name_x
#                         if self.spatial.grid.is_vectorized:
#                             self.spatial.grid.y.dimensions[0].name = name_y
#                             self.spatial.grid.y.name = name_y
#                             self.spatial.grid.x.dimensions[0].name = name_x
#                             self.spatial.grid.x.name = name_x
#                         else:
#                             for idx, d in enumerate([self.spatial.grid.y, self.spatial.grid.x]):
#                                 name_tuple = (name_y, name_x)
#                                 d.name = name_tuple[idx]
#                                 for dsubname, dsub in zip(name_tuple, d.dimensions):
#                                     dsub.name = dsubname
#
#                 # Update the other dimension names.
#                 for name in ['time', 'level', 'realization']:
#                     try:
#                         new_name = self._dimension_schema[name][1]
#                     except IndexError:
#                         pass
#                     else:
#                         target = getattr(self, name)
#                         if target is not None:
#                             target.dimensions[0].name = new_name
#                             target.name = new_name
#
#     def _set_dimension_variable_(self, name, value, axis):
#         if value is not None:
#             assert isinstance(value, Variable)
#             value = copy(value)
#             value.attrs = value.attrs.copy()
#             value.dimensions = deepcopy(value.dimensions)
#             value.attrs['axis'] = value.attrs.pop('axis', axis)
#         setattr(self, name, value)
#         self.sync()
#
#     def write_netcdf(self, *args, **kwargs):
#         # tdk: test temporal
#         # tdk: test field
#         self.sync()
#         vc = VariableCollection(attrs=self.attrs, variables=self.fields.itervalues())
#         for v in self.extra.itervalues():
#             vc.add_variable(v)
#         if self.realization is not None:
#             vc.add_variable(self.realization)
#         if self.level is not None:
#             vc.add_variable(self.level)
#         if self.spatial is not None:
#             vc.add_variable(self.spatial.grid)
#         if self.time is not None:
#             vc.add_variable(self.time)
#         vc.write_netcdf(*args, **kwargs)
#
#
# def set_getitem_field_bundle(fb, slc):
#     if fb.spatial is not None:
#         spatial_slice = [None] * fb.spatial.ndim
#     for k, v in slc.items():
#         if k in fb._dimension_schema['y']:
#             spatial_slice[0] = v
#         elif k in fb._dimension_schema['x']:
#             spatial_slice[1] = v
#         elif k in fb._dimension_schema['n_geom']:
#             spatial_slice[0] = v
#         else:
#             for d, poss in fb._dimension_schema.items():
#                 if k in poss:
#                     setattr(fb, d, getattr(fb, d)[v])
#                     break
#     if fb.spatial is not None:
#         fb.spatial = fb.spatial[spatial_slice]
#
