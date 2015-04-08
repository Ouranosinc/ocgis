from collections import OrderedDict
import os
from copy import deepcopy

import ogr
from shapely import wkb
import fiona

from ocgis import env
from ocgis.interface.base.dimension.spatial import SpatialDimension


class ShpCabinetIterator(object):
    """
    Iterate over geometries from a shapefile specified by ``key`` or ``path``.

    >>> sc = ShpCabinet()
    >>> geoms = sc.iter_geoms('state_boundaries', select_uid=[1, 48])
    >>> len(list(geoms))
    2

    :param key: Unique key identifier for a shapefile contained in the ShpCabinet directory.
    :type key: str

    >>> key = 'state_boundaries'

    :param select_uid: Sequence of unique identifiers to select from the target shapefile.
    :type select_uid: sequence

    >>> select_uid = [23, 24]

    :param path: Path to the target shapefile to iterate over. If ``key`` is provided it will override ``path``.
    :type path: str

    >>> path = '/path/to/shapefile.shp'

    :param bool load_geoms: If ``False``, do not load geometries, excluding the ``'geom'`` key from the output
     dictionary.
    :param bool as_spatial_dimension: If ``True``, yield spatial dimension (:class:`~ocgis.SpatialDimension`)
     objects.
    :param str uid: The name of the attribute containing the unique identifier. If ``None``,
     :attr:`ocgis.env.DEFAULT_GEOM_UID` will be used if present. If no unique identifier is found, add one with name
     :attr:`ocgis.env.DEFAULT_GEOM_UID`.
    :param str select_sql_where: A string suitable for insertion into a SQL WHERE statement. See http://www.gdal.org/ogr_sql.html
     for documentation (section titled "WHERE").

    >>> select_sql_where = 'STATE_NAME = "Wisconsin"'

    :raises: ValueError, RuntimeError
    :rtype: dict
    """

    def __init__(self, key=None, select_uid=None, path=None, load_geoms=True, as_spatial_dimension=False, uid=None,
                 select_sql_where=None):
        self.key = key
        self.path = path
        self.select_uid = select_uid
        self.load_geoms = load_geoms
        self.as_spatial_dimension = as_spatial_dimension
        self.uid = uid
        self.select_sql_where = select_sql_where
        self.sc = ShpCabinet()

    def __iter__(self):
        """
        Return an iterator as from :meth:`ocgis.ShpCabinet.iter_geoms`.
        """

        for row in self.sc.iter_geoms(key=self.key, select_uid=self.select_uid, path=self.path,
                                      load_geoms=self.load_geoms, as_spatial_dimension=self.as_spatial_dimension,
                                      uid=self.uid, select_sql_where=self.select_sql_where):
            yield row

    def __len__(self):
        # get the path to the output shapefile
        shp_path = self.sc._get_path_by_key_or_direct_path_(key=self.key, path=self.path)

        if self.select_uid is not None:
            ret = len(self.select_uid)
        else:
            # get the geometries
            ds = ogr.Open(shp_path)
            try:
                features = self.sc._get_features_object_(ds, uid=self.uid, select_uid=self.select_uid,
                                                         select_sql_where=self.select_sql_where)
                ret = len(features)
            finally:
                ds.Destroy()
                ds = None
        return ret


class ShpCabinet(object):
    """
    A utility object designed for accessing shapefiles stored in a locally accessible location.

    >>> # Adjust location of :class:`ocgis.ShpCabinet` search directory.
    >>> import ocgis
    ...
    >>> ocgis.env.DIR_SHPCABINET = '/path/to/local/shapefile/directory'
    >>> sc = ShpCabinet()
    >>> # List the shapefiles available.
    >>> sc.keys()
    ['state_boundaries', 'mi_watersheds', 'world_countries']
    >>> # Load geometries from the shapefile.
    >>> geoms = sc.get_geoms('state_boundaries')

    :param path: Absolute path the directory holding shapefile folders. Defaults to :attr:`ocgis.env.DIR_SHPCABINET`.
    :type path: str
    """

    def __init__(self, path=None):
        self._path = path or env.DIR_SHPCABINET

    @property
    def path(self):
        if self._path is None:
            msg = 'A path value is required. Either pass a path to the constructor or set ocgis.env.DIR_SHPCABINET.'
            raise ValueError(msg)
        elif not os.path.exists(self._path):
            raise ValueError('Specified path to ShpCabinet folder does not exist: {0}'.format(self._path))
        return self._path

    def keys(self):
        """Return a list of the shapefile keys contained in the search directory.
        
        :rtype: list of str
        """
        ret = []
        for dirpath, dirnames, filenames in os.walk(self.path):
            for fn in filenames:
                if fn.endswith('shp'):
                    ret.append(os.path.splitext(fn)[0])
        return ret

    def get_meta(self, key=None, path=None):
        path = path or self.get_shp_path(key)
        with fiona.open(path, 'r') as source:
            return source.meta

    def get_shp_path(self, key):
        return self._get_path_(key, ext='shp')

    def get_cfg_path(self, key):
        return self._get_path_(key, ext='cfg')

    def _get_path_(self, key, ext='shp'):
        ret = None
        for dirpath, dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                if filename.endswith(ext) and os.path.splitext(filename)[0] == key:
                    ret = os.path.join(dirpath, filename)
                    return ret
        if ret is None:
            msg = 'a shapefile with key "{0}" was not found under the directory: {1}'.format(key, self.path)
            raise ValueError(msg)

    def iter_geoms(self, key=None, select_uid=None, path=None, load_geoms=True, as_spatial_dimension=False,
                   uid=None, select_sql_where=None):
        """
        See documentation for :class:`~ocgis.util.shp_cabinet.ShpCabinetIterator`.
        """

        # ensure select ugid is in ascending order
        if select_uid is not None:
            test_select_ugid = list(deepcopy(select_uid))
            test_select_ugid.sort()
            if test_select_ugid != list(select_uid):
                raise ValueError('"select_uid" must be sorted in ascending order.')

        # get the path to the output shapefile
        shp_path = self._get_path_by_key_or_direct_path_(key=key, path=path)

        # get the source CRS
        meta = self.get_meta(path=shp_path)

        # open the target shapefile
        ds = ogr.Open(shp_path)
        try:
            # return the features iterator
            features = self._get_features_object_(ds, uid=uid, select_uid=select_uid, select_sql_where=select_sql_where)
            build = True
            for ctr, feature in enumerate(features):
                if load_geoms:
                    yld = {'geom': wkb.loads(feature.geometry().ExportToWkb())}
                else:
                    yld = {}
                items = feature.items()
                properties = OrderedDict([(key, items[key]) for key in feature.keys()])
                yld.update({'properties': properties, 'meta': meta})

                if build:
                    uid, add_uid = get_uid_from_properties(properties, uid)
                    build = False

                # add the unique identifier if required
                if add_uid:
                    properties[uid] = ctr + 1
                # ensure the unique identifier is an integer
                else:
                    properties[uid] = int(properties[uid])

                if as_spatial_dimension:
                    yld = SpatialDimension.from_records([yld], crs=yld['meta']['crs'], uid=uid)

                yield yld
            try:
                assert ctr >= 0
            except UnboundLocalError:
                # occurs if there were not feature returned by the iterator. raise a more clear exception.
                msg = 'No features returned from target shapefile. Were features appropriately selected?'
                raise ValueError(msg)
        finally:
            # close the dataset object
            ds.Destroy()
            ds = None

    def _get_path_by_key_or_direct_path_(self, key=None, path=None):
        """
        :param str key:
        :param str path:
        """
        # path to the target shapefile
        if key is None:
            try:
                assert path != None
            except AssertionError:
                raise ValueError('If no key is passed, then a path must be provided.')
            shp_path = path
        else:
            shp_path = self.get_shp_path(key)
        # make sure requested geometry exists
        if not os.path.exists(shp_path):
            msg = 'Requested geometry with path "{0}" does not exist in the file system.'.format(shp_path)
            raise RuntimeError(msg)
        return shp_path

    @staticmethod
    def _get_features_object_(ds, uid=None, select_uid=None, select_sql_where=None):
        """
        :param ds: Path to shapefile.
        :type ds: Open OGR dataset object
        :param str uid: The unique identifier to use during SQL selection.
        :param sequence select_uid: Sequence of integers mapping to unique geometry identifiers.
        :param str select_sql_where: A string suitable for insertion into a SQL WHERE statement. See http://www.gdal.org/ogr_sql.html
         for documentation (section titled "WHERE").

        >>> select_sql_where = 'STATE_NAME = "Wisconsin"'

        :returns: A layer object with selection applied if ``select_uid`` is not ``None``.
        :rtype: :class:`osgeo.ogr.Layer`
        """

        # get the geometries
        lyr = ds.GetLayerByIndex(0)
        lyr.ResetReading()
        if select_uid is not None or select_sql_where is not None:
            lyr_name = lyr.GetName()
            if select_sql_where is not None:
                sql = 'SELECT * FROM "{0}" WHERE {1}'.format(lyr_name, select_sql_where)
            elif select_uid is not None:
                # if no uid is provided, use the default
                if uid is None:
                    uid = env.DEFAULT_GEOM_UID
                # format where statement different for singletons
                if len(select_uid) == 1:
                    sql_where = '{0} = {1}'.format(uid, select_uid[0])
                else:
                    sql_where = '{0} IN {1}'.format(uid, tuple(select_uid))
                sql = 'SELECT * FROM "{0}" WHERE {1}'.format(lyr_name, sql_where)
            features = ds.ExecuteSQL(sql)
        else:
            features = lyr
        return features


def get_uid_from_properties(properties, uid):
    """
    :param dict properties: A dictionary of properties with key corresponding to property names.
    :param str uid: The unique identifier to search for. If ``None``, default to :attr:`~ocgis.env.DEFAULT_GEOM_UID`.
    :returns: A tuple containing the name of the unique identifier and a boolean indicating if a unique identifier needs
     to be generated.
    :rtype: (str, bool)
    :raises: ValueError
    """

    if uid is None:
        if env.DEFAULT_GEOM_UID in properties:
            uid = env.DEFAULT_GEOM_UID
    else:
        if uid not in properties:
            msg = 'The unique identifier "{0}" was not found in the properties dictionary: {1}'.format(uid, properties)
            raise ValueError(msg)

    # if there is a unique identifier in the properties dictionary, ensure it may be converted to an integer data type.
    if uid is not None:
        try:
            int(properties[uid])
        except ValueError:
            msg = 'The unique identifier "{0}" may not be converted to an integer data type.'.format(uid)
            raise ValueError(msg)

    # if there is no unique identifier, the default identifier name will be assigned.
    if uid is None:
        uid = env.DEFAULT_GEOM_UID
        add_uid = True
    else:
        add_uid = False

    return uid, add_uid
