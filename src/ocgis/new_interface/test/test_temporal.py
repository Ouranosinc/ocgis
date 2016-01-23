import datetime
import itertools
import os
from collections import deque
from copy import deepcopy
from datetime import datetime as dt
from netCDF4 import date2num, num2date
from unittest import SkipTest

import numpy as np
from netcdftime import netcdftime

from ocgis import constants
from ocgis.api.parms.definition import CalcGrouping
from ocgis.api.request.base import RequestDataset
from ocgis.exc import CannotFormatTimeError, IncompleteSeasonError
from ocgis.new_interface.temporal import get_datetime_conversion_state, get_datetime_from_months_time_units, \
    get_datetime_from_template_time_units, get_difference_in_months, get_is_interannual, get_num_from_months_time_units, \
    get_origin_datetime_from_months_units, get_sorted_seasons, TemporalVariable, iter_boolean_groups_from_time_regions, \
    TemporalGroupVariable, get_time_regions
from ocgis.new_interface.test.test_new_interface import AbstractTestNewInterface
from ocgis.new_interface.variable import Variable, SourcedVariable
from ocgis.test.base import attr
from ocgis.util.helpers import get_date_list
from ocgis.util.units import get_units_object, get_are_units_equal, get_are_units_equivalent


class AbstractTestTemporal(AbstractTestNewInterface):
    @property
    def value_template_units(self):
        return np.array([19710101.9375, 19710102.9375, 19710103.9375, 19710104.9375, 19710105.9375])

    @property
    def value_template_units_no_decimal(self):
        return np.array([20000101., 20000102., 20000103., 20000104., 20000105., 20000106.])


class Test(AbstractTestTemporal):
    def test_get_datetime_conversion_state(self):
        archetypes = [45.5, datetime.datetime(2000, 1, 1), netcdftime.datetime(2000, 4, 5)]
        for archetype in archetypes:
            res = get_datetime_conversion_state(archetype)
            try:
                self.assertFalse(res)
            except AssertionError:
                self.assertEqual(type(archetype), float)

    def test_get_datetime_from_months_time_units(self):
        units = "months since 1978-12"
        vec = range(0, 36)
        datetimes = get_datetime_from_months_time_units(vec, units)
        test_datetimes = [datetime.datetime(1978, 12, 16, 0, 0), datetime.datetime(1979, 1, 16, 0, 0),
                          datetime.datetime(1979, 2, 16, 0, 0), datetime.datetime(1979, 3, 16, 0, 0),
                          datetime.datetime(1979, 4, 16, 0, 0), datetime.datetime(1979, 5, 16, 0, 0),
                          datetime.datetime(1979, 6, 16, 0, 0), datetime.datetime(1979, 7, 16, 0, 0),
                          datetime.datetime(1979, 8, 16, 0, 0), datetime.datetime(1979, 9, 16, 0, 0),
                          datetime.datetime(1979, 10, 16, 0, 0), datetime.datetime(1979, 11, 16, 0, 0),
                          datetime.datetime(1979, 12, 16, 0, 0), datetime.datetime(1980, 1, 16, 0, 0),
                          datetime.datetime(1980, 2, 16, 0, 0), datetime.datetime(1980, 3, 16, 0, 0),
                          datetime.datetime(1980, 4, 16, 0, 0), datetime.datetime(1980, 5, 16, 0, 0),
                          datetime.datetime(1980, 6, 16, 0, 0), datetime.datetime(1980, 7, 16, 0, 0),
                          datetime.datetime(1980, 8, 16, 0, 0), datetime.datetime(1980, 9, 16, 0, 0),
                          datetime.datetime(1980, 10, 16, 0, 0), datetime.datetime(1980, 11, 16, 0, 0),
                          datetime.datetime(1980, 12, 16, 0, 0), datetime.datetime(1981, 1, 16, 0, 0),
                          datetime.datetime(1981, 2, 16, 0, 0), datetime.datetime(1981, 3, 16, 0, 0),
                          datetime.datetime(1981, 4, 16, 0, 0), datetime.datetime(1981, 5, 16, 0, 0),
                          datetime.datetime(1981, 6, 16, 0, 0), datetime.datetime(1981, 7, 16, 0, 0),
                          datetime.datetime(1981, 8, 16, 0, 0), datetime.datetime(1981, 9, 16, 0, 0),
                          datetime.datetime(1981, 10, 16, 0, 0), datetime.datetime(1981, 11, 16, 0, 0)]
        self.assertNumpyAll(datetimes, np.array(test_datetimes))

    def test_get_datetime_from_template_time_units(self):
        ret = get_datetime_from_template_time_units(self.value_template_units)
        self.assertEqual(ret.shape, self.value_template_units.shape)
        self.assertEqual(ret[2], datetime.datetime(1971, 1, 3, 22, 30))

        ret = get_datetime_from_template_time_units(self.value_template_units_no_decimal)
        self.assertEqual(ret.shape, self.value_template_units_no_decimal.shape)
        self.assertEqual(ret[2], datetime.datetime(2000, 1, 3))

    def test_get_difference_in_months(self):
        distance = get_difference_in_months(datetime.datetime(1978, 12, 1), datetime.datetime(1979, 3, 1))
        self.assertEqual(distance, 3)
        distance = get_difference_in_months(datetime.datetime(1978, 12, 1), datetime.datetime(1978, 7, 1))
        self.assertEqual(distance, -5)
        distance = get_difference_in_months(datetime.datetime(1978, 12, 1), datetime.datetime(1978, 12, 1))
        self.assertEqual(distance, 0)

    def test_get_is_interannual(self):
        self.assertTrue(get_is_interannual([11, 12, 1]))
        self.assertFalse(get_is_interannual([10, 11, 12]))

    def test_get_num_from_months_time_units_1d_array(self):
        units = "months since 1978-12"
        vec = range(0, 36)
        datetimes = get_datetime_from_months_time_units(vec, units)
        num = get_num_from_months_time_units(datetimes, units, dtype=np.int32)
        self.assertNumpyAll(num, np.array(vec, dtype=np.int32))
        self.assertEqual(num.dtype, np.int32)

    def test_get_origin_datetime_from_months_units(self):
        units = "months since 1978-12"
        self.assertEqual(get_origin_datetime_from_months_units(units), datetime.datetime(1978, 12, 1))
        units = "months since 1979-1-1 0"
        self.assertEqual(get_origin_datetime_from_months_units(units), datetime.datetime(1979, 1, 1))

    def test_get_sorted_seasons(self):
        calc_grouping = [[9, 10, 11], [12, 1, 2], [6, 7, 8]]
        methods = ['max', 'min']

        for method in methods:
            for perm in itertools.permutations(calc_grouping, r=3):
                ret = get_sorted_seasons(perm, method=method)
                if method == 'max':
                    self.assertEqual(ret, [[6, 7, 8], [9, 10, 11], [12, 1, 2]])
                else:
                    self.assertEqual(ret, [[12, 1, 2], [6, 7, 8], [9, 10, 11]])

    def test_iter_boolean_groups_from_time_regions(self):
        time_regions = [[{'month': [12], 'year': [1900]}, {'month': [2, 1], 'year': [1901]}]]
        yield_subset = True
        raise_if_incomplete = False

        start = datetime.datetime(1900, 1, 1)
        end = datetime.datetime(1902, 12, 31)
        value = self.get_time_series(start, end)
        tvar = TemporalVariable(value=value, units=constants.DEFAULT_TEMPORAL_UNITS)

        itr = iter_boolean_groups_from_time_regions(time_regions, tvar, yield_subset=yield_subset,
                                                    raise_if_incomplete=raise_if_incomplete)
        itr = list(itr)
        self.assertEqual(len(itr), 1)
        for dgroup, sub in itr:
            self.assertEqual(sub.value[0].year, 1900)
            self.assertEqual(sub.value[0].month, 12)


class TestTemporalVariable(AbstractTestTemporal):
    def get_temporalvariable(self, add_bounds=True, start=None, stop=None, days=1, name=None, format_time=True):
        start = start or datetime.datetime(1899, 1, 1, 12)
        stop = stop or datetime.datetime(1901, 12, 31, 12)
        dates = get_date_list(start, stop, days=days)
        if add_bounds:
            delta = datetime.timedelta(hours=12)
            lower = np.array(dates) - delta
            upper = np.array(dates) + delta
            bounds = np.empty((lower.shape[0], 2), dtype=object)
            bounds[:, 0] = lower
            bounds[:, 1] = upper
            bounds = Variable('time_bounds', value=bounds)
        else:
            bounds = None
        td = TemporalVariable(value=dates, bounds=bounds, name=name, format_time=format_time)
        return td

    def get_template_units(self):
        units = 'day as %Y%m%d.%f'
        td = TemporalVariable(value=self.value_template_units, units=units, calendar='proleptic_gregorian')
        return td

    def test_init(self):
        td = TemporalVariable(value=[datetime.datetime(2000, 1, 1)])
        self.assertEqual(td.name, constants.DEFAULT_TEMPORAL_NAME)
        self.assertEqual(td.calendar, constants.DEFAULT_TEMPORAL_CALENDAR)
        self.assertEqual(td.units, constants.DEFAULT_TEMPORAL_UNITS)
        self.assertIsInstance(td, TemporalVariable)
        self.assertFalse(td._has_months_units)
        self.assertTrue(td.format_time)

        td = TemporalVariable(value=[datetime.datetime(2000, 1, 1)], units="months since 1978-12")
        self.assertTrue(td._has_months_units)

    def test_360_day_calendar(self):
        months = range(1, 13)
        days = range(1, 31)
        vec = []
        for month in months:
            for day in days:
                vec.append(netcdftime.datetime(2000, month, day))
        num = date2num(vec, 'days since 1900-01-01', calendar='360_day')
        td = TemporalVariable(value=num, calendar='360_day', units='days since 1900-01-01')
        self.assertNumpyAll(np.ma.array(vec), td.value_datetime)

    def test_bounds_datetime_and_bounds_numtime(self):
        value_datetime = np.array([dt(2000, 1, 15), dt(2000, 2, 15)])
        bounds_datetime = np.array([[dt(2000, 1, 1), dt(2000, 2, 1)],
                                    [dt(2000, 2, 1), dt(2000, 3, 1)]])
        value = date2num(value_datetime, constants.DEFAULT_TEMPORAL_UNITS, calendar=constants.DEFAULT_TEMPORAL_CALENDAR)
        bounds_num = date2num(bounds_datetime, constants.DEFAULT_TEMPORAL_UNITS,
                              calendar=constants.DEFAULT_TEMPORAL_CALENDAR)
        bounds_options = [None, bounds_num, bounds_datetime]
        value_options = [value, value, value_datetime]
        for format_time in [True, False]:
            for value, bounds in zip(value_options, bounds_options):
                if bounds is not None:
                    bounds = Variable(name='time_bounds', value=bounds)
                td = TemporalVariable(value=value, bounds=bounds, format_time=format_time)
                if bounds is not None:
                    try:
                        self.assertNumpyAll(td.bounds_datetime.masked_value, np.ma.array(bounds_datetime))
                    except CannotFormatTimeError:
                        self.assertFalse(format_time)
                    self.assertNumpyAll(td.bounds_numtime.masked_value, np.ma.array(bounds_num))
                else:
                    self.assertIsNone(td.bounds)
                    self.assertIsNone(td.bounds_numtime)
                    try:
                        self.assertIsNone(td.bounds_datetime)
                    except CannotFormatTimeError:
                        self.assertFalse(format_time)

    @attr('cfunits')
    def test_cfunits(self):
        temporal = TemporalVariable(value=[4, 5, 6], units='days since 1900-1-1')
        self.assertEqual(temporal.cfunits.calendar, temporal.calendar)

    @attr('cfunits')
    def test_cfunits_conform(self):
        # Test with template units.
        td = self.get_template_units()
        value_numtime_original = td.value_numtime.copy()
        value_datetime_original = td.value_datetime.copy()
        td.cfunits_conform(get_units_object('days since 1920-1-1', calendar=td.calendar))
        self.assertLess(td.value_numtime.mean(), value_numtime_original.mean())
        self.assertNumpyAll(value_datetime_original, td.value_datetime)
        self.assertEqual(td.units, 'days since 1920-1-1')
        self.assertEqual(td.calendar, 'proleptic_gregorian')

        d = get_units_object('days since 1900-1-1', calendar=constants.DEFAULT_TEMPORAL_CALENDAR)
        td = TemporalVariable(value=[4, 5, 6], units='days since 1901-1-1')
        td.cfunits_conform(d)
        self.assertTrue(get_are_units_equal((td.cfunits, d)))

        td = TemporalVariable(value=[4, 5, 6])
        self.assertIsNone(td.conform_units_to)

        # Test with template units.
        units = get_units_object('days since 1960-1-1', calendar='proleptic_gregorian')
        td = self.get_template_units()
        td.cfunits_conform(units)
        self.assertAlmostEqual(td.value_numtime.mean(), 4020.9375)
        self.assertEqual(str(td.units), str(units).split('calendar=')[0].strip())

    @attr('data', 'cfunits')
    def test_cfunits_conform_data(self):

        def _get_temporal_variable_(conform_units_to=None):
            rd = self.get_request_dataset()
            bounds = SourcedVariable(name='time_bnds', request_dataset=rd)
            tv = TemporalVariable(name='time', request_dataset=rd, bounds=bounds, conform_units_to=conform_units_to)
            return tv

        target = get_units_object('days since 1949-1-1', calendar='365_day')
        temporal = _get_temporal_variable_(conform_units_to=target)
        temporal_orig = _get_temporal_variable_()
        self.assertTrue(get_are_units_equivalent((target, temporal.cfunits, temporal_orig.cfunits)))
        self.assertEqual(temporal.calendar, '365_day')
        self.assertEqual(temporal_orig.calendar, '365_day')
        self.assertNumpyNotAll(temporal.value, temporal_orig.value)
        self.assertNumpyAll(temporal.value_datetime, temporal_orig.value_datetime)

    def test_extent_datetime_and_extent_numtime(self):
        value_numtime = np.array([6000., 6001., 6002])
        value_datetime = TemporalVariable(value=value_numtime).value_datetime

        for format_time in [True, False]:
            for value in [value_numtime, value_datetime]:
                td = TemporalVariable(value=value, format_time=format_time)
                try:
                    self.assertEqual(td.extent_datetime, (min(value_datetime), max(value_datetime)))
                except CannotFormatTimeError:
                    self.assertFalse(format_time)
                self.assertEqual(td.extent_numtime, (6000., 6002.))

    def test_getitem(self):
        td = self.get_temporalvariable()
        elements = [td.bounds_datetime, td.bounds_numtime]
        for element in elements:
            self.assertIsNotNone(element)
        sub = td[2]
        elements = [sub.bounds_datetime, sub.bounds_numtime]
        for element in elements:
            self.assertEqual(element.shape, (1, 2))

        td = self.get_temporalvariable()
        self.assertIsNotNone(td.value_datetime)
        self.assertIsNotNone(td.value_numtime)
        sub = td[3]
        self.assertEqual(sub.value_datetime.shape, (1,))
        self.assertEqual(sub.value_numtime.shape, (1,))

    def test_get_between(self):
        keywords = dict(as_datetime=[False, True])

        for k in self.iter_product_keywords(keywords, as_namedtuple=True):
            td = self.get_temporalvariable()
            if not k.as_datetime:
                td._value = td.value_numtime
                td._bounds = td.bounds_numtime
                td._value_datetime = None
                td._bounds_datetime = None
                self.assertTrue(get_datetime_conversion_state(td.value[0]))
            res = td.get_between(dt(1899, 1, 4, 12, 0), dt(1899, 1, 10, 12, 0), return_indices=False)
            self.assertEqual(res.shape, (7,))
            self.assertIsNone(td._value_datetime)
            self.assertIsNone(td._bounds_datetime)

        # test with template units
        td = self.get_template_units()
        lower = datetime.datetime(1971, 1, 2)
        upper = datetime.datetime(1971, 1, 5)
        sub = td.get_between(lower, upper)
        self.assertEqual(sub.shape, (3,))

    def test_get_boolean_groups_from_time_regions(self):
        dates = get_date_list(dt(2012, 1, 1), dt(2013, 12, 31), 1)
        seasons = [[3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 1, 2]]
        td = TemporalVariable(value=dates)
        time_regions = get_time_regions(seasons, dates, raise_if_incomplete=False)

        dgroups = list(iter_boolean_groups_from_time_regions(time_regions, td))
        # the last winter season is not complete as it does not have enough years
        self.assertEqual(len(dgroups), 7)

        to_test = []
        for dgroup in dgroups:
            sub = td[dgroup]
            # (upper and lower values of time vector, count of elements in time group, the middle value of the vector)
            to_test.append([sub.extent, sub.shape[0], sub[sub.shape[0] / 2].value[0]])
        correct = [[(datetime.datetime(2012, 3, 1, 0, 0), datetime.datetime(2012, 5, 31, 0, 0)), 92,
                    datetime.datetime(2012, 4, 16, 0, 0)],
                   [(datetime.datetime(2012, 6, 1, 0, 0), datetime.datetime(2012, 8, 31, 0, 0)), 92,
                    datetime.datetime(2012, 7, 17, 0, 0)],
                   [(datetime.datetime(2012, 9, 1, 0, 0), datetime.datetime(2012, 11, 30, 0, 0)), 91,
                    datetime.datetime(2012, 10, 16, 0, 0)],
                   [(datetime.datetime(2012, 12, 1, 0, 0), datetime.datetime(2013, 2, 28, 0, 0)), 90,
                    datetime.datetime(2013, 1, 15, 0, 0)],
                   [(datetime.datetime(2013, 3, 1, 0, 0), datetime.datetime(2013, 5, 31, 0, 0)), 92,
                    datetime.datetime(2013, 4, 16, 0, 0)],
                   [(datetime.datetime(2013, 6, 1, 0, 0), datetime.datetime(2013, 8, 31, 0, 0)), 92,
                    datetime.datetime(2013, 7, 17, 0, 0)],
                   [(datetime.datetime(2013, 9, 1, 0, 0), datetime.datetime(2013, 11, 30, 0, 0)), 91,
                    datetime.datetime(2013, 10, 16, 0, 0)]]
        self.assertEqual(to_test, correct)

    def test_get_datetime(self):
        td = TemporalVariable(value=[5, 6])
        dts = np.array([dt(2000, 1, 15, 12), dt(2000, 2, 15, 12)])
        arr = date2num(dts, 'days since 0001-01-01 00:00:00')
        res = td.get_datetime(arr)
        self.assertNumpyAll(dts, res)

        td = TemporalVariable(value=[5, 6], units='months since 1978-12')
        res = td.get_datetime(td.value)
        self.assertEqual(res[0], dt(1979, 5, 16))

        units = 'days since 0001-01-01 00:00:00'
        calendar = '365_day'
        ndt = netcdftime.datetime
        ndts = np.array([ndt(0000, 2, 30), ndt(0000, 2, 31)])
        narr = date2num(ndts, units, calendar=calendar)
        td = TemporalVariable(value=narr, units=units, calendar=calendar)
        res = td.get_datetime(td.value)
        self.assertTrue(all([isinstance(element, ndt) for element in res.flat]))

        # test with template units
        td = self.get_template_units()
        self.assertIsNotNone(td.value_datetime)
        self.assertEqual(td.value_datetime[2], datetime.datetime(1971, 1, 3, 22, 30))
        td2 = TemporalVariable(value=td.value_numtime, units=td.units, calendar='proleptic_gregorian')
        self.assertNumpyAll(td.value_datetime, td2.value_datetime)

    def test_getiter(self):
        raise SkipTest
        for format_time in [True, False]:
            td = self.get_temporalvariable(name='time', format_time=format_time)
            for idx, values in td.get_iter():
                to_test = (values['day'], values['month'], values['year'])
                try:
                    self.assertTrue(all([element is not None for element in to_test]))
                    self.assertIsInstance(values['time'], dt)
                except AssertionError:
                    self.assertTrue(all([element is None for element in to_test]))
                    self.assertIsInstance(values['time'], float)

    def test_get_numtime(self):
        units_options = [constants.DEFAULT_TEMPORAL_UNITS, 'months since 1960-5']
        value_options = [np.array([5000., 5001]), np.array([5, 6, 7])]
        for units, value in zip(units_options, value_options):
            td = TemporalVariable(value=value, units=units)
            nums = td.get_numtime(td.value_datetime)
            self.assertNumpyAll(nums, value)

    def test_get_grouping(self):
        tv = self.get_temporalvariable()
        td = tv.get_between(datetime.datetime(1900, 1, 1), datetime.datetime(1900, 12, 31, 23, 59))
        self.assertEqual(td.bounds.shape, (365, 2))
        tgd = td.get_grouping(['year'])
        self.assertEqual(tgd.value, np.array([datetime.datetime(1900, 7, 1)]))

        # Test with a 360_day calendar and 3-hourly data.
        start = 0.0625
        stop = 719.9375
        step = 0.125
        values = np.arange(start, stop + step, step)
        td = TemporalVariable(value=values, calendar='360_day', units='days since 1960-01-01')
        for g in CalcGrouping.iter_possible():
            tgd = td.get_grouping(g)
            self.assertIsInstance(tgd, TemporalGroupVariable)
            # Test calendar is maintained when creating a group dimension.
            self.assertEqual(tgd.calendar, '360_day')

        value = [dt(2012, 1, 1), dt(2012, 1, 2)]
        td = TemporalVariable(value=value)
        tgd = td.get_grouping(['month'])
        self.assertEqual(tuple(tgd.date_parts[0]), (None, 1, None, None, None, None))
        self.assertTrue(tgd.dgroups[0].all())

    def test_get_grouping_all(self):
        for b in [True, False]:
            td = self.get_temporalvariable(add_bounds=b)
            tgd = td.get_grouping('all')
            self.assertEqual(tgd.dgroups, [slice(None)])
            self.assertEqual(td.value[546], tgd.value[0])
            if b:
                self.assertNumpyAll(tgd.bounds.masked_value, np.ma.array([[datetime.datetime(1899, 1, 1),
                                                                           datetime.datetime(1902, 1, 1)]]))
            else:
                self.assertNumpyAll(tgd.bounds.masked_value, np.ma.array([[datetime.datetime(1899, 1, 1, 12),
                                                                           datetime.datetime(1901, 12, 31, 12)]]))

    def test_get_grouping_other(self):
        tdim = self.get_temporalvariable()
        grouping = [[12, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], 'year']
        new_bounds, date_parts, repr_dt, dgroups = tdim._get_grouping_other_(grouping)

        actual_repr_dt = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x0c\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07k\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07k\x04\x10\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07k\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07k\n\x10\x00\x00\x00\x00\x00\x00\x85Rq\x0bh\x07U\n\x07l\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\x0ch\x07U\n\x07l\x04\x10\x00\x00\x00\x00\x00\x00\x85Rq\rh\x07U\n\x07l\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq\x0eh\x07U\n\x07l\n\x10\x00\x00\x00\x00\x00\x00\x85Rq\x0fh\x07U\n\x07m\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\x10h\x07U\n\x07m\x04\x10\x00\x00\x00\x00\x00\x00\x85Rq\x11h\x07U\n\x07m\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq\x12h\x07U\n\x07m\n\x10\x00\x00\x00\x00\x00\x00\x85Rq\x13etb.')
        self.assertNumpyAll(repr_dt, actual_repr_dt)

        actual_new_bounds = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x0cK\x02\x86cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07k\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07l\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07k\x03\x01\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07k\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x0bh\x07U\n\x07k\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x0ch\x07U\n\x07k\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\rh\x07U\n\x07k\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\x0eh\x07U\n\x07k\x0c\x01\x00\x00\x00\x00\x00\x00\x85Rq\x0fh\x07U\n\x07l\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x10h\x07U\n\x07m\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x11h\x07U\n\x07l\x03\x01\x00\x00\x00\x00\x00\x00\x85Rq\x12h\x07U\n\x07l\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x13h\x07U\n\x07l\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x14h\x07U\n\x07l\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\x15h\x07U\n\x07l\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\x16h\x07U\n\x07l\x0c\x01\x00\x00\x00\x00\x00\x00\x85Rq\x17h\x07U\n\x07m\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x18h\x07U\n\x07n\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x19h\x07U\n\x07m\x03\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1ah\x07U\n\x07m\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1bh\x07U\n\x07m\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1ch\x07U\n\x07m\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1dh\x07U\n\x07m\t\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1eh\x07U\n\x07m\x0c\x01\x00\x00\x00\x00\x00\x00\x85Rq\x1fetb.')
        self.assertNumpyAll(new_bounds, actual_new_bounds)

        actual_dgroups = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01MG\x04\x85cnumpy\ndtype\nq\x04U\x02b1K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00tb\x89TG\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00tb.')
        self.assertNumpyAll(actual_dgroups, dgroups[4])

        actual_date_parts = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x0c\x85cnumpy\ndtype\nq\x04U\x03V16K\x00K\x01\x87Rq\x05(K\x03U\x01|NU\x06monthsq\x06U\x04yearq\x07\x86q\x08}q\t(h\x06h\x04U\x02O8K\x00K\x01\x87Rq\n(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tbK\x00\x86h\x07h\x04U\x02i8K\x00K\x01\x87Rq\x0b(K\x03U\x01<NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00tbK\x08\x86uK\x10K\x01K\x1btb\x89]q\x0c(]q\r(K\x0cK\x01K\x02eMk\x07\x86q\x0e]q\x0f(K\x03K\x04K\x05eMk\x07\x86q\x10]q\x11(K\x06K\x07K\x08eMk\x07\x86q\x12]q\x13(K\tK\nK\x0beMk\x07\x86q\x14h\rMl\x07\x86q\x15h\x0fMl\x07\x86q\x16h\x11Ml\x07\x86q\x17h\x13Ml\x07\x86q\x18h\rMm\x07\x86q\x19h\x0fMm\x07\x86q\x1ah\x11Mm\x07\x86q\x1bh\x13Mm\x07\x86q\x1cetb.')
        self.assertNumpyAll(actual_date_parts, date_parts)

    @attr('data')
    def test_get_grouping_seasonal(self):
        dates = get_date_list(dt(2012, 4, 1), dt(2012, 10, 31), 1)
        td = TemporalVariable(value=dates)

        # standard seasonal group
        calc_grouping = [[6, 7, 8]]
        tg = td.get_grouping(calc_grouping)
        self.assertEqual(len(tg.value), 1)
        selected_months = [s.month for s in td.value[tg.dgroups[0]].flat]
        not_selected_months = [s.month for s in td.value[np.invert(tg.dgroups[0])]]
        self.assertEqual(set(calc_grouping[0]), set(selected_months))
        self.assertFalse(set(not_selected_months).issubset(set(calc_grouping[0])))

        # seasons different sizes
        calc_grouping = [[4, 5, 6, 7], [8, 9, 10]]
        tg = td.get_grouping(calc_grouping)
        self.assertEqual(len(tg.value), 2)
        self.assertNumpyAll(tg.dgroups[0], np.invert(tg.dgroups[1]))

        # crosses year boundary
        calc_grouping = [[11, 12, 1]]
        dates = get_date_list(dt(2012, 10, 1), dt(2013, 3, 31), 1)
        td = TemporalVariable(value=dates)
        tg = td.get_grouping(calc_grouping)
        selected_months = [s.month for s in td.value[tg.dgroups[0]].flat]
        self.assertEqual(set(calc_grouping[0]), set(selected_months))
        self.assertEqual(tg.value[0], dt(2012, 12, 16))

        # grab real data
        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        td = TemporalVariable(value=field.temporal.value_datetime)
        tg = td.get_grouping([[3, 4, 5]])
        self.assertEqual(tg.value[0], dt(2005, 4, 16))

    def test_get_grouping_seasonal_empty_with_year_missing_month(self):
        dt1 = datetime.datetime(1900, 01, 01)
        dt2 = datetime.datetime(1903, 1, 31)
        dates = get_date_list(dt1, dt2, days=1)
        td = TemporalVariable(value=dates)
        group = [[12, 1, 2], 'unique']
        tg = td.get_grouping(group)
        # There should be a month missing from the last season (february) and it should not be considered complete.
        self.assertEqual(tg.value.shape[0], 2)

    @attr('data')
    def test_get_grouping_seasonal_real_data_all_seasons(self):
        """Test with real data and full seasons."""

        calc_grouping = [[12, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
        rd = self.test_data.get_rd('cancm4_tas')
        field = rd.get()
        tgd = field.temporal.get_grouping(calc_grouping)
        self.assertEqual(tgd.shape, (4,))
        self.assertEqual([xx[1] for xx in calc_grouping], [xx.month for xx in tgd.value.flat])
        self.assertEqual(set([xx.day for xx in tgd.value.flat]), {constants.CALC_MONTH_CENTROID})
        self.assertEqual([2006, 2005, 2005, 2005], [xx.year for xx in tgd.value.flat])
        self.assertNumpyAll(tgd.bounds_numtime,
                            np.array([[55115.0, 58765.0], [55174.0, 58551.0], [55266.0, 58643.0], [55358.0, 58734.0]]))

    def test_get_grouping_seasonal_unique_flag(self):
        """Test the unique flag for seasonal groups."""

        dates = get_date_list(dt(2012, 1, 1), dt(2013, 12, 31), 1)
        td = TemporalVariable(value=dates)
        calc_grouping = [[6, 7, 8], 'unique']
        tg = td.get_grouping(calc_grouping)

        time_region = {'year': [2012], 'month': [6, 7, 8]}
        sub1, idx1 = td.get_time_region(time_region, return_indices=True)
        time_region = {'year': [2013], 'month': [6, 7, 8]}
        sub2, idx2 = td.get_time_region(time_region, return_indices=True)
        base_select = np.zeros(td.shape[0], dtype=bool)
        dgroups = deque()

        for software, manual in itertools.izip(tg.dgroups, dgroups):
            self.assertNumpyAll(software, manual)
        self.assertEqual(len(tg.dgroups), 2)
        self.assertEqual(tg.value.tolist(),
                         [datetime.datetime(2012, 7, 17, 0, 0), datetime.datetime(2013, 7, 17, 0, 0)])
        self.assertEqual(tg.bounds.value.tolist(),
                         [[datetime.datetime(2012, 6, 1, 0, 0), datetime.datetime(2012, 8, 31, 0, 0)],
                          [datetime.datetime(2013, 6, 1, 0, 0), datetime.datetime(2013, 8, 31, 0, 0)]])

        dgroup1 = base_select.copy()
        dgroup1[idx1] = True
        dgroup2 = base_select.copy()
        dgroup2[idx2] = True

        dgroups.append(dgroup1)
        dgroups.append(dgroup2)

        tg = td.get_grouping([[6, 7, 8], 'year'])
        for ii in range(len(tg.dgroups)):
            self.assertNumpyAll(tg.dgroups[ii], dgroups[ii])
        self.assertEqual(len(tg.dgroups), len(dgroups))

    def test_get_grouping_seasonal_unique_flag_all_seasons(self):
        """Test unique flag with all seasons."""

        start = datetime.datetime(1900, 1, 1)
        end = datetime.datetime(1902, 12, 31)
        ret = self.get_time_series(start, end)
        calc_grouping = [[12, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], 'unique']
        td = TemporalVariable(value=ret)
        group = td.get_grouping(calc_grouping)

        for idx in range(group.shape[0]):
            bounds_lower = group.bounds.value[idx, 0]
            bounds_upper = group.bounds.value[idx, 1]

            sub = td[group.dgroups[idx]]
            self.assertEqual(sub.masked_value.compressed().min(), bounds_lower)
            self.assertEqual(sub.masked_value.compressed().max(), bounds_upper)

        self.assertEqual(group.value.tolist(),
                         [datetime.datetime(1900, 4, 16, 0, 0), datetime.datetime(1900, 7, 17, 0, 0),
                          datetime.datetime(1900, 10, 16, 0, 0), datetime.datetime(1901, 1, 15, 0, 0),
                          datetime.datetime(1901, 4, 16, 0, 0), datetime.datetime(1901, 7, 17, 0, 0),
                          datetime.datetime(1901, 10, 16, 0, 0), datetime.datetime(1902, 1, 15, 0, 0),
                          datetime.datetime(1902, 4, 16, 0, 0), datetime.datetime(1902, 7, 17, 0, 0),
                          datetime.datetime(1902, 10, 16, 0, 0)])
        self.assertEqual(group.bounds.value.tolist(),
                         [[datetime.datetime(1900, 3, 1, 0, 0), datetime.datetime(1900, 5, 31, 0, 0)],
                          [datetime.datetime(1900, 6, 1, 0, 0), datetime.datetime(1900, 8, 31, 0, 0)],
                          [datetime.datetime(1900, 9, 1, 0, 0), datetime.datetime(1900, 11, 30, 0, 0)],
                          [datetime.datetime(1900, 12, 1, 0, 0), datetime.datetime(1901, 2, 28, 0, 0)],
                          [datetime.datetime(1901, 3, 1, 0, 0), datetime.datetime(1901, 5, 31, 0, 0)],
                          [datetime.datetime(1901, 6, 1, 0, 0), datetime.datetime(1901, 8, 31, 0, 0)],
                          [datetime.datetime(1901, 9, 1, 0, 0), datetime.datetime(1901, 11, 30, 0, 0)],
                          [datetime.datetime(1901, 12, 1, 0, 0), datetime.datetime(1902, 2, 28, 0, 0)],
                          [datetime.datetime(1902, 3, 1, 0, 0), datetime.datetime(1902, 5, 31, 0, 0)],
                          [datetime.datetime(1902, 6, 1, 0, 0), datetime.datetime(1902, 8, 31, 0, 0)],
                          [datetime.datetime(1902, 9, 1, 0, 0), datetime.datetime(1902, 11, 30, 0, 0)]])

    def test_get_grouping_seasonal_unique_flag_winter_season(self):
        """Test with a single winter season using the unique flag."""

        dt1 = datetime.datetime(1900, 01, 01)
        dt2 = datetime.datetime(1902, 12, 31)
        dates = get_date_list(dt1, dt2, days=1)
        td = TemporalVariable(value=dates)
        group = [[12, 1, 2], 'unique']
        tg = td.get_grouping(group)
        self.assertEqual(tg.value.shape[0], 2)
        self.assertEqual(tg.bounds.value.tolist(),
                         [[datetime.datetime(1900, 12, 1, 0, 0), datetime.datetime(1901, 2, 28, 0, 0)],
                          [datetime.datetime(1901, 12, 1, 0, 0), datetime.datetime(1902, 2, 28, 0, 0)]])

    def test_get_grouping_seasonal_year_flag(self):
        # test with year flag
        dates = get_date_list(dt(2012, 1, 1), dt(2013, 12, 31), 1)
        td = TemporalVariable(value=dates)
        calc_grouping = [[6, 7, 8], 'year']
        tg = td.get_grouping(calc_grouping)
        self.assertEqual(tg.value.shape[0], 2)

        # '[datetime.datetime(2012, 7, 16, 0, 0) datetime.datetime(2013, 7, 16, 0, 0)]'
        actual = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x02\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdc\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdd\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq\tetb.')
        self.assertNumpyAll(tg.masked_value, np.ma.array(actual))

        # '[datetime.datetime(2012, 6, 1, 0, 0) datetime.datetime(2012, 6, 2, 0, 0)\n datetime.datetime(2012, 6, 3, 0, 0) datetime.datetime(2012, 6, 4, 0, 0)\n datetime.datetime(2012, 6, 5, 0, 0) datetime.datetime(2012, 6, 6, 0, 0)\n datetime.datetime(2012, 6, 7, 0, 0) datetime.datetime(2012, 6, 8, 0, 0)\n datetime.datetime(2012, 6, 9, 0, 0) datetime.datetime(2012, 6, 10, 0, 0)\n datetime.datetime(2012, 6, 11, 0, 0) datetime.datetime(2012, 6, 12, 0, 0)\n datetime.datetime(2012, 6, 13, 0, 0) datetime.datetime(2012, 6, 14, 0, 0)\n datetime.datetime(2012, 6, 15, 0, 0) datetime.datetime(2012, 6, 16, 0, 0)\n datetime.datetime(2012, 6, 17, 0, 0) datetime.datetime(2012, 6, 18, 0, 0)\n datetime.datetime(2012, 6, 19, 0, 0) datetime.datetime(2012, 6, 20, 0, 0)\n datetime.datetime(2012, 6, 21, 0, 0) datetime.datetime(2012, 6, 22, 0, 0)\n datetime.datetime(2012, 6, 23, 0, 0) datetime.datetime(2012, 6, 24, 0, 0)\n datetime.datetime(2012, 6, 25, 0, 0) datetime.datetime(2012, 6, 26, 0, 0)\n datetime.datetime(2012, 6, 27, 0, 0) datetime.datetime(2012, 6, 28, 0, 0)\n datetime.datetime(2012, 6, 29, 0, 0) datetime.datetime(2012, 6, 30, 0, 0)\n datetime.datetime(2012, 7, 1, 0, 0) datetime.datetime(2012, 7, 2, 0, 0)\n datetime.datetime(2012, 7, 3, 0, 0) datetime.datetime(2012, 7, 4, 0, 0)\n datetime.datetime(2012, 7, 5, 0, 0) datetime.datetime(2012, 7, 6, 0, 0)\n datetime.datetime(2012, 7, 7, 0, 0) datetime.datetime(2012, 7, 8, 0, 0)\n datetime.datetime(2012, 7, 9, 0, 0) datetime.datetime(2012, 7, 10, 0, 0)\n datetime.datetime(2012, 7, 11, 0, 0) datetime.datetime(2012, 7, 12, 0, 0)\n datetime.datetime(2012, 7, 13, 0, 0) datetime.datetime(2012, 7, 14, 0, 0)\n datetime.datetime(2012, 7, 15, 0, 0) datetime.datetime(2012, 7, 16, 0, 0)\n datetime.datetime(2012, 7, 17, 0, 0) datetime.datetime(2012, 7, 18, 0, 0)\n datetime.datetime(2012, 7, 19, 0, 0) datetime.datetime(2012, 7, 20, 0, 0)\n datetime.datetime(2012, 7, 21, 0, 0) datetime.datetime(2012, 7, 22, 0, 0)\n datetime.datetime(2012, 7, 23, 0, 0) datetime.datetime(2012, 7, 24, 0, 0)\n datetime.datetime(2012, 7, 25, 0, 0) datetime.datetime(2012, 7, 26, 0, 0)\n datetime.datetime(2012, 7, 27, 0, 0) datetime.datetime(2012, 7, 28, 0, 0)\n datetime.datetime(2012, 7, 29, 0, 0) datetime.datetime(2012, 7, 30, 0, 0)\n datetime.datetime(2012, 7, 31, 0, 0) datetime.datetime(2012, 8, 1, 0, 0)\n datetime.datetime(2012, 8, 2, 0, 0) datetime.datetime(2012, 8, 3, 0, 0)\n datetime.datetime(2012, 8, 4, 0, 0) datetime.datetime(2012, 8, 5, 0, 0)\n datetime.datetime(2012, 8, 6, 0, 0) datetime.datetime(2012, 8, 7, 0, 0)\n datetime.datetime(2012, 8, 8, 0, 0) datetime.datetime(2012, 8, 9, 0, 0)\n datetime.datetime(2012, 8, 10, 0, 0) datetime.datetime(2012, 8, 11, 0, 0)\n datetime.datetime(2012, 8, 12, 0, 0) datetime.datetime(2012, 8, 13, 0, 0)\n datetime.datetime(2012, 8, 14, 0, 0) datetime.datetime(2012, 8, 15, 0, 0)\n datetime.datetime(2012, 8, 16, 0, 0) datetime.datetime(2012, 8, 17, 0, 0)\n datetime.datetime(2012, 8, 18, 0, 0) datetime.datetime(2012, 8, 19, 0, 0)\n datetime.datetime(2012, 8, 20, 0, 0) datetime.datetime(2012, 8, 21, 0, 0)\n datetime.datetime(2012, 8, 22, 0, 0) datetime.datetime(2012, 8, 23, 0, 0)\n datetime.datetime(2012, 8, 24, 0, 0) datetime.datetime(2012, 8, 25, 0, 0)\n datetime.datetime(2012, 8, 26, 0, 0) datetime.datetime(2012, 8, 27, 0, 0)\n datetime.datetime(2012, 8, 28, 0, 0) datetime.datetime(2012, 8, 29, 0, 0)\n datetime.datetime(2012, 8, 30, 0, 0) datetime.datetime(2012, 8, 31, 0, 0)]'
        actual = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\\\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdc\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdc\x06\x02\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07\xdc\x06\x03\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07\xdc\x06\x04\x00\x00\x00\x00\x00\x00\x85Rq\x0bh\x07U\n\x07\xdc\x06\x05\x00\x00\x00\x00\x00\x00\x85Rq\x0ch\x07U\n\x07\xdc\x06\x06\x00\x00\x00\x00\x00\x00\x85Rq\rh\x07U\n\x07\xdc\x06\x07\x00\x00\x00\x00\x00\x00\x85Rq\x0eh\x07U\n\x07\xdc\x06\x08\x00\x00\x00\x00\x00\x00\x85Rq\x0fh\x07U\n\x07\xdc\x06\t\x00\x00\x00\x00\x00\x00\x85Rq\x10h\x07U\n\x07\xdc\x06\n\x00\x00\x00\x00\x00\x00\x85Rq\x11h\x07U\n\x07\xdc\x06\x0b\x00\x00\x00\x00\x00\x00\x85Rq\x12h\x07U\n\x07\xdc\x06\x0c\x00\x00\x00\x00\x00\x00\x85Rq\x13h\x07U\n\x07\xdc\x06\r\x00\x00\x00\x00\x00\x00\x85Rq\x14h\x07U\n\x07\xdc\x06\x0e\x00\x00\x00\x00\x00\x00\x85Rq\x15h\x07U\n\x07\xdc\x06\x0f\x00\x00\x00\x00\x00\x00\x85Rq\x16h\x07U\n\x07\xdc\x06\x10\x00\x00\x00\x00\x00\x00\x85Rq\x17h\x07U\n\x07\xdc\x06\x11\x00\x00\x00\x00\x00\x00\x85Rq\x18h\x07U\n\x07\xdc\x06\x12\x00\x00\x00\x00\x00\x00\x85Rq\x19h\x07U\n\x07\xdc\x06\x13\x00\x00\x00\x00\x00\x00\x85Rq\x1ah\x07U\n\x07\xdc\x06\x14\x00\x00\x00\x00\x00\x00\x85Rq\x1bh\x07U\n\x07\xdc\x06\x15\x00\x00\x00\x00\x00\x00\x85Rq\x1ch\x07U\n\x07\xdc\x06\x16\x00\x00\x00\x00\x00\x00\x85Rq\x1dh\x07U\n\x07\xdc\x06\x17\x00\x00\x00\x00\x00\x00\x85Rq\x1eh\x07U\n\x07\xdc\x06\x18\x00\x00\x00\x00\x00\x00\x85Rq\x1fh\x07U\n\x07\xdc\x06\x19\x00\x00\x00\x00\x00\x00\x85Rq h\x07U\n\x07\xdc\x06\x1a\x00\x00\x00\x00\x00\x00\x85Rq!h\x07U\n\x07\xdc\x06\x1b\x00\x00\x00\x00\x00\x00\x85Rq"h\x07U\n\x07\xdc\x06\x1c\x00\x00\x00\x00\x00\x00\x85Rq#h\x07U\n\x07\xdc\x06\x1d\x00\x00\x00\x00\x00\x00\x85Rq$h\x07U\n\x07\xdc\x06\x1e\x00\x00\x00\x00\x00\x00\x85Rq%h\x07U\n\x07\xdc\x07\x01\x00\x00\x00\x00\x00\x00\x85Rq&h\x07U\n\x07\xdc\x07\x02\x00\x00\x00\x00\x00\x00\x85Rq\'h\x07U\n\x07\xdc\x07\x03\x00\x00\x00\x00\x00\x00\x85Rq(h\x07U\n\x07\xdc\x07\x04\x00\x00\x00\x00\x00\x00\x85Rq)h\x07U\n\x07\xdc\x07\x05\x00\x00\x00\x00\x00\x00\x85Rq*h\x07U\n\x07\xdc\x07\x06\x00\x00\x00\x00\x00\x00\x85Rq+h\x07U\n\x07\xdc\x07\x07\x00\x00\x00\x00\x00\x00\x85Rq,h\x07U\n\x07\xdc\x07\x08\x00\x00\x00\x00\x00\x00\x85Rq-h\x07U\n\x07\xdc\x07\t\x00\x00\x00\x00\x00\x00\x85Rq.h\x07U\n\x07\xdc\x07\n\x00\x00\x00\x00\x00\x00\x85Rq/h\x07U\n\x07\xdc\x07\x0b\x00\x00\x00\x00\x00\x00\x85Rq0h\x07U\n\x07\xdc\x07\x0c\x00\x00\x00\x00\x00\x00\x85Rq1h\x07U\n\x07\xdc\x07\r\x00\x00\x00\x00\x00\x00\x85Rq2h\x07U\n\x07\xdc\x07\x0e\x00\x00\x00\x00\x00\x00\x85Rq3h\x07U\n\x07\xdc\x07\x0f\x00\x00\x00\x00\x00\x00\x85Rq4h\x07U\n\x07\xdc\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq5h\x07U\n\x07\xdc\x07\x11\x00\x00\x00\x00\x00\x00\x85Rq6h\x07U\n\x07\xdc\x07\x12\x00\x00\x00\x00\x00\x00\x85Rq7h\x07U\n\x07\xdc\x07\x13\x00\x00\x00\x00\x00\x00\x85Rq8h\x07U\n\x07\xdc\x07\x14\x00\x00\x00\x00\x00\x00\x85Rq9h\x07U\n\x07\xdc\x07\x15\x00\x00\x00\x00\x00\x00\x85Rq:h\x07U\n\x07\xdc\x07\x16\x00\x00\x00\x00\x00\x00\x85Rq;h\x07U\n\x07\xdc\x07\x17\x00\x00\x00\x00\x00\x00\x85Rq<h\x07U\n\x07\xdc\x07\x18\x00\x00\x00\x00\x00\x00\x85Rq=h\x07U\n\x07\xdc\x07\x19\x00\x00\x00\x00\x00\x00\x85Rq>h\x07U\n\x07\xdc\x07\x1a\x00\x00\x00\x00\x00\x00\x85Rq?h\x07U\n\x07\xdc\x07\x1b\x00\x00\x00\x00\x00\x00\x85Rq@h\x07U\n\x07\xdc\x07\x1c\x00\x00\x00\x00\x00\x00\x85RqAh\x07U\n\x07\xdc\x07\x1d\x00\x00\x00\x00\x00\x00\x85RqBh\x07U\n\x07\xdc\x07\x1e\x00\x00\x00\x00\x00\x00\x85RqCh\x07U\n\x07\xdc\x07\x1f\x00\x00\x00\x00\x00\x00\x85RqDh\x07U\n\x07\xdc\x08\x01\x00\x00\x00\x00\x00\x00\x85RqEh\x07U\n\x07\xdc\x08\x02\x00\x00\x00\x00\x00\x00\x85RqFh\x07U\n\x07\xdc\x08\x03\x00\x00\x00\x00\x00\x00\x85RqGh\x07U\n\x07\xdc\x08\x04\x00\x00\x00\x00\x00\x00\x85RqHh\x07U\n\x07\xdc\x08\x05\x00\x00\x00\x00\x00\x00\x85RqIh\x07U\n\x07\xdc\x08\x06\x00\x00\x00\x00\x00\x00\x85RqJh\x07U\n\x07\xdc\x08\x07\x00\x00\x00\x00\x00\x00\x85RqKh\x07U\n\x07\xdc\x08\x08\x00\x00\x00\x00\x00\x00\x85RqLh\x07U\n\x07\xdc\x08\t\x00\x00\x00\x00\x00\x00\x85RqMh\x07U\n\x07\xdc\x08\n\x00\x00\x00\x00\x00\x00\x85RqNh\x07U\n\x07\xdc\x08\x0b\x00\x00\x00\x00\x00\x00\x85RqOh\x07U\n\x07\xdc\x08\x0c\x00\x00\x00\x00\x00\x00\x85RqPh\x07U\n\x07\xdc\x08\r\x00\x00\x00\x00\x00\x00\x85RqQh\x07U\n\x07\xdc\x08\x0e\x00\x00\x00\x00\x00\x00\x85RqRh\x07U\n\x07\xdc\x08\x0f\x00\x00\x00\x00\x00\x00\x85RqSh\x07U\n\x07\xdc\x08\x10\x00\x00\x00\x00\x00\x00\x85RqTh\x07U\n\x07\xdc\x08\x11\x00\x00\x00\x00\x00\x00\x85RqUh\x07U\n\x07\xdc\x08\x12\x00\x00\x00\x00\x00\x00\x85RqVh\x07U\n\x07\xdc\x08\x13\x00\x00\x00\x00\x00\x00\x85RqWh\x07U\n\x07\xdc\x08\x14\x00\x00\x00\x00\x00\x00\x85RqXh\x07U\n\x07\xdc\x08\x15\x00\x00\x00\x00\x00\x00\x85RqYh\x07U\n\x07\xdc\x08\x16\x00\x00\x00\x00\x00\x00\x85RqZh\x07U\n\x07\xdc\x08\x17\x00\x00\x00\x00\x00\x00\x85Rq[h\x07U\n\x07\xdc\x08\x18\x00\x00\x00\x00\x00\x00\x85Rq\\h\x07U\n\x07\xdc\x08\x19\x00\x00\x00\x00\x00\x00\x85Rq]h\x07U\n\x07\xdc\x08\x1a\x00\x00\x00\x00\x00\x00\x85Rq^h\x07U\n\x07\xdc\x08\x1b\x00\x00\x00\x00\x00\x00\x85Rq_h\x07U\n\x07\xdc\x08\x1c\x00\x00\x00\x00\x00\x00\x85Rq`h\x07U\n\x07\xdc\x08\x1d\x00\x00\x00\x00\x00\x00\x85Rqah\x07U\n\x07\xdc\x08\x1e\x00\x00\x00\x00\x00\x00\x85Rqbh\x07U\n\x07\xdc\x08\x1f\x00\x00\x00\x00\x00\x00\x85Rqcetb.')
        sub0 = td.masked_value[tg.dgroups[0]]
        self.assertNumpyAll(sub0, np.ma.array(actual))

        # '[datetime.datetime(2013, 6, 1, 0, 0) datetime.datetime(2013, 6, 2, 0, 0)\n datetime.datetime(2013, 6, 3, 0, 0) datetime.datetime(2013, 6, 4, 0, 0)\n datetime.datetime(2013, 6, 5, 0, 0) datetime.datetime(2013, 6, 6, 0, 0)\n datetime.datetime(2013, 6, 7, 0, 0) datetime.datetime(2013, 6, 8, 0, 0)\n datetime.datetime(2013, 6, 9, 0, 0) datetime.datetime(2013, 6, 10, 0, 0)\n datetime.datetime(2013, 6, 11, 0, 0) datetime.datetime(2013, 6, 12, 0, 0)\n datetime.datetime(2013, 6, 13, 0, 0) datetime.datetime(2013, 6, 14, 0, 0)\n datetime.datetime(2013, 6, 15, 0, 0) datetime.datetime(2013, 6, 16, 0, 0)\n datetime.datetime(2013, 6, 17, 0, 0) datetime.datetime(2013, 6, 18, 0, 0)\n datetime.datetime(2013, 6, 19, 0, 0) datetime.datetime(2013, 6, 20, 0, 0)\n datetime.datetime(2013, 6, 21, 0, 0) datetime.datetime(2013, 6, 22, 0, 0)\n datetime.datetime(2013, 6, 23, 0, 0) datetime.datetime(2013, 6, 24, 0, 0)\n datetime.datetime(2013, 6, 25, 0, 0) datetime.datetime(2013, 6, 26, 0, 0)\n datetime.datetime(2013, 6, 27, 0, 0) datetime.datetime(2013, 6, 28, 0, 0)\n datetime.datetime(2013, 6, 29, 0, 0) datetime.datetime(2013, 6, 30, 0, 0)\n datetime.datetime(2013, 7, 1, 0, 0) datetime.datetime(2013, 7, 2, 0, 0)\n datetime.datetime(2013, 7, 3, 0, 0) datetime.datetime(2013, 7, 4, 0, 0)\n datetime.datetime(2013, 7, 5, 0, 0) datetime.datetime(2013, 7, 6, 0, 0)\n datetime.datetime(2013, 7, 7, 0, 0) datetime.datetime(2013, 7, 8, 0, 0)\n datetime.datetime(2013, 7, 9, 0, 0) datetime.datetime(2013, 7, 10, 0, 0)\n datetime.datetime(2013, 7, 11, 0, 0) datetime.datetime(2013, 7, 12, 0, 0)\n datetime.datetime(2013, 7, 13, 0, 0) datetime.datetime(2013, 7, 14, 0, 0)\n datetime.datetime(2013, 7, 15, 0, 0) datetime.datetime(2013, 7, 16, 0, 0)\n datetime.datetime(2013, 7, 17, 0, 0) datetime.datetime(2013, 7, 18, 0, 0)\n datetime.datetime(2013, 7, 19, 0, 0) datetime.datetime(2013, 7, 20, 0, 0)\n datetime.datetime(2013, 7, 21, 0, 0) datetime.datetime(2013, 7, 22, 0, 0)\n datetime.datetime(2013, 7, 23, 0, 0) datetime.datetime(2013, 7, 24, 0, 0)\n datetime.datetime(2013, 7, 25, 0, 0) datetime.datetime(2013, 7, 26, 0, 0)\n datetime.datetime(2013, 7, 27, 0, 0) datetime.datetime(2013, 7, 28, 0, 0)\n datetime.datetime(2013, 7, 29, 0, 0) datetime.datetime(2013, 7, 30, 0, 0)\n datetime.datetime(2013, 7, 31, 0, 0) datetime.datetime(2013, 8, 1, 0, 0)\n datetime.datetime(2013, 8, 2, 0, 0) datetime.datetime(2013, 8, 3, 0, 0)\n datetime.datetime(2013, 8, 4, 0, 0) datetime.datetime(2013, 8, 5, 0, 0)\n datetime.datetime(2013, 8, 6, 0, 0) datetime.datetime(2013, 8, 7, 0, 0)\n datetime.datetime(2013, 8, 8, 0, 0) datetime.datetime(2013, 8, 9, 0, 0)\n datetime.datetime(2013, 8, 10, 0, 0) datetime.datetime(2013, 8, 11, 0, 0)\n datetime.datetime(2013, 8, 12, 0, 0) datetime.datetime(2013, 8, 13, 0, 0)\n datetime.datetime(2013, 8, 14, 0, 0) datetime.datetime(2013, 8, 15, 0, 0)\n datetime.datetime(2013, 8, 16, 0, 0) datetime.datetime(2013, 8, 17, 0, 0)\n datetime.datetime(2013, 8, 18, 0, 0) datetime.datetime(2013, 8, 19, 0, 0)\n datetime.datetime(2013, 8, 20, 0, 0) datetime.datetime(2013, 8, 21, 0, 0)\n datetime.datetime(2013, 8, 22, 0, 0) datetime.datetime(2013, 8, 23, 0, 0)\n datetime.datetime(2013, 8, 24, 0, 0) datetime.datetime(2013, 8, 25, 0, 0)\n datetime.datetime(2013, 8, 26, 0, 0) datetime.datetime(2013, 8, 27, 0, 0)\n datetime.datetime(2013, 8, 28, 0, 0) datetime.datetime(2013, 8, 29, 0, 0)\n datetime.datetime(2013, 8, 30, 0, 0) datetime.datetime(2013, 8, 31, 0, 0)]'
        actual = np.loads(
            '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\\\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdd\x06\x01\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdd\x06\x02\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07\xdd\x06\x03\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07\xdd\x06\x04\x00\x00\x00\x00\x00\x00\x85Rq\x0bh\x07U\n\x07\xdd\x06\x05\x00\x00\x00\x00\x00\x00\x85Rq\x0ch\x07U\n\x07\xdd\x06\x06\x00\x00\x00\x00\x00\x00\x85Rq\rh\x07U\n\x07\xdd\x06\x07\x00\x00\x00\x00\x00\x00\x85Rq\x0eh\x07U\n\x07\xdd\x06\x08\x00\x00\x00\x00\x00\x00\x85Rq\x0fh\x07U\n\x07\xdd\x06\t\x00\x00\x00\x00\x00\x00\x85Rq\x10h\x07U\n\x07\xdd\x06\n\x00\x00\x00\x00\x00\x00\x85Rq\x11h\x07U\n\x07\xdd\x06\x0b\x00\x00\x00\x00\x00\x00\x85Rq\x12h\x07U\n\x07\xdd\x06\x0c\x00\x00\x00\x00\x00\x00\x85Rq\x13h\x07U\n\x07\xdd\x06\r\x00\x00\x00\x00\x00\x00\x85Rq\x14h\x07U\n\x07\xdd\x06\x0e\x00\x00\x00\x00\x00\x00\x85Rq\x15h\x07U\n\x07\xdd\x06\x0f\x00\x00\x00\x00\x00\x00\x85Rq\x16h\x07U\n\x07\xdd\x06\x10\x00\x00\x00\x00\x00\x00\x85Rq\x17h\x07U\n\x07\xdd\x06\x11\x00\x00\x00\x00\x00\x00\x85Rq\x18h\x07U\n\x07\xdd\x06\x12\x00\x00\x00\x00\x00\x00\x85Rq\x19h\x07U\n\x07\xdd\x06\x13\x00\x00\x00\x00\x00\x00\x85Rq\x1ah\x07U\n\x07\xdd\x06\x14\x00\x00\x00\x00\x00\x00\x85Rq\x1bh\x07U\n\x07\xdd\x06\x15\x00\x00\x00\x00\x00\x00\x85Rq\x1ch\x07U\n\x07\xdd\x06\x16\x00\x00\x00\x00\x00\x00\x85Rq\x1dh\x07U\n\x07\xdd\x06\x17\x00\x00\x00\x00\x00\x00\x85Rq\x1eh\x07U\n\x07\xdd\x06\x18\x00\x00\x00\x00\x00\x00\x85Rq\x1fh\x07U\n\x07\xdd\x06\x19\x00\x00\x00\x00\x00\x00\x85Rq h\x07U\n\x07\xdd\x06\x1a\x00\x00\x00\x00\x00\x00\x85Rq!h\x07U\n\x07\xdd\x06\x1b\x00\x00\x00\x00\x00\x00\x85Rq"h\x07U\n\x07\xdd\x06\x1c\x00\x00\x00\x00\x00\x00\x85Rq#h\x07U\n\x07\xdd\x06\x1d\x00\x00\x00\x00\x00\x00\x85Rq$h\x07U\n\x07\xdd\x06\x1e\x00\x00\x00\x00\x00\x00\x85Rq%h\x07U\n\x07\xdd\x07\x01\x00\x00\x00\x00\x00\x00\x85Rq&h\x07U\n\x07\xdd\x07\x02\x00\x00\x00\x00\x00\x00\x85Rq\'h\x07U\n\x07\xdd\x07\x03\x00\x00\x00\x00\x00\x00\x85Rq(h\x07U\n\x07\xdd\x07\x04\x00\x00\x00\x00\x00\x00\x85Rq)h\x07U\n\x07\xdd\x07\x05\x00\x00\x00\x00\x00\x00\x85Rq*h\x07U\n\x07\xdd\x07\x06\x00\x00\x00\x00\x00\x00\x85Rq+h\x07U\n\x07\xdd\x07\x07\x00\x00\x00\x00\x00\x00\x85Rq,h\x07U\n\x07\xdd\x07\x08\x00\x00\x00\x00\x00\x00\x85Rq-h\x07U\n\x07\xdd\x07\t\x00\x00\x00\x00\x00\x00\x85Rq.h\x07U\n\x07\xdd\x07\n\x00\x00\x00\x00\x00\x00\x85Rq/h\x07U\n\x07\xdd\x07\x0b\x00\x00\x00\x00\x00\x00\x85Rq0h\x07U\n\x07\xdd\x07\x0c\x00\x00\x00\x00\x00\x00\x85Rq1h\x07U\n\x07\xdd\x07\r\x00\x00\x00\x00\x00\x00\x85Rq2h\x07U\n\x07\xdd\x07\x0e\x00\x00\x00\x00\x00\x00\x85Rq3h\x07U\n\x07\xdd\x07\x0f\x00\x00\x00\x00\x00\x00\x85Rq4h\x07U\n\x07\xdd\x07\x10\x00\x00\x00\x00\x00\x00\x85Rq5h\x07U\n\x07\xdd\x07\x11\x00\x00\x00\x00\x00\x00\x85Rq6h\x07U\n\x07\xdd\x07\x12\x00\x00\x00\x00\x00\x00\x85Rq7h\x07U\n\x07\xdd\x07\x13\x00\x00\x00\x00\x00\x00\x85Rq8h\x07U\n\x07\xdd\x07\x14\x00\x00\x00\x00\x00\x00\x85Rq9h\x07U\n\x07\xdd\x07\x15\x00\x00\x00\x00\x00\x00\x85Rq:h\x07U\n\x07\xdd\x07\x16\x00\x00\x00\x00\x00\x00\x85Rq;h\x07U\n\x07\xdd\x07\x17\x00\x00\x00\x00\x00\x00\x85Rq<h\x07U\n\x07\xdd\x07\x18\x00\x00\x00\x00\x00\x00\x85Rq=h\x07U\n\x07\xdd\x07\x19\x00\x00\x00\x00\x00\x00\x85Rq>h\x07U\n\x07\xdd\x07\x1a\x00\x00\x00\x00\x00\x00\x85Rq?h\x07U\n\x07\xdd\x07\x1b\x00\x00\x00\x00\x00\x00\x85Rq@h\x07U\n\x07\xdd\x07\x1c\x00\x00\x00\x00\x00\x00\x85RqAh\x07U\n\x07\xdd\x07\x1d\x00\x00\x00\x00\x00\x00\x85RqBh\x07U\n\x07\xdd\x07\x1e\x00\x00\x00\x00\x00\x00\x85RqCh\x07U\n\x07\xdd\x07\x1f\x00\x00\x00\x00\x00\x00\x85RqDh\x07U\n\x07\xdd\x08\x01\x00\x00\x00\x00\x00\x00\x85RqEh\x07U\n\x07\xdd\x08\x02\x00\x00\x00\x00\x00\x00\x85RqFh\x07U\n\x07\xdd\x08\x03\x00\x00\x00\x00\x00\x00\x85RqGh\x07U\n\x07\xdd\x08\x04\x00\x00\x00\x00\x00\x00\x85RqHh\x07U\n\x07\xdd\x08\x05\x00\x00\x00\x00\x00\x00\x85RqIh\x07U\n\x07\xdd\x08\x06\x00\x00\x00\x00\x00\x00\x85RqJh\x07U\n\x07\xdd\x08\x07\x00\x00\x00\x00\x00\x00\x85RqKh\x07U\n\x07\xdd\x08\x08\x00\x00\x00\x00\x00\x00\x85RqLh\x07U\n\x07\xdd\x08\t\x00\x00\x00\x00\x00\x00\x85RqMh\x07U\n\x07\xdd\x08\n\x00\x00\x00\x00\x00\x00\x85RqNh\x07U\n\x07\xdd\x08\x0b\x00\x00\x00\x00\x00\x00\x85RqOh\x07U\n\x07\xdd\x08\x0c\x00\x00\x00\x00\x00\x00\x85RqPh\x07U\n\x07\xdd\x08\r\x00\x00\x00\x00\x00\x00\x85RqQh\x07U\n\x07\xdd\x08\x0e\x00\x00\x00\x00\x00\x00\x85RqRh\x07U\n\x07\xdd\x08\x0f\x00\x00\x00\x00\x00\x00\x85RqSh\x07U\n\x07\xdd\x08\x10\x00\x00\x00\x00\x00\x00\x85RqTh\x07U\n\x07\xdd\x08\x11\x00\x00\x00\x00\x00\x00\x85RqUh\x07U\n\x07\xdd\x08\x12\x00\x00\x00\x00\x00\x00\x85RqVh\x07U\n\x07\xdd\x08\x13\x00\x00\x00\x00\x00\x00\x85RqWh\x07U\n\x07\xdd\x08\x14\x00\x00\x00\x00\x00\x00\x85RqXh\x07U\n\x07\xdd\x08\x15\x00\x00\x00\x00\x00\x00\x85RqYh\x07U\n\x07\xdd\x08\x16\x00\x00\x00\x00\x00\x00\x85RqZh\x07U\n\x07\xdd\x08\x17\x00\x00\x00\x00\x00\x00\x85Rq[h\x07U\n\x07\xdd\x08\x18\x00\x00\x00\x00\x00\x00\x85Rq\\h\x07U\n\x07\xdd\x08\x19\x00\x00\x00\x00\x00\x00\x85Rq]h\x07U\n\x07\xdd\x08\x1a\x00\x00\x00\x00\x00\x00\x85Rq^h\x07U\n\x07\xdd\x08\x1b\x00\x00\x00\x00\x00\x00\x85Rq_h\x07U\n\x07\xdd\x08\x1c\x00\x00\x00\x00\x00\x00\x85Rq`h\x07U\n\x07\xdd\x08\x1d\x00\x00\x00\x00\x00\x00\x85Rqah\x07U\n\x07\xdd\x08\x1e\x00\x00\x00\x00\x00\x00\x85Rqbh\x07U\n\x07\xdd\x08\x1f\x00\x00\x00\x00\x00\x00\x85Rqcetb.')
        sub1 = td.masked_value[tg.dgroups[1]]
        self.assertNumpyAll(sub1, np.ma.array(actual))

        # test crossing year boundary
        for calc_grouping in [[[12, 1, 2], 'year'], ['year', [12, 1, 2]]]:
            tg = td.get_grouping(calc_grouping)

            # '[datetime.datetime(2012, 1, 16, 0, 0) datetime.datetime(2013, 1, 16, 0, 0)]'
            self.assertNumpyAll(tg.masked_value, np.ma.array(np.loads(
                '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x02\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdc\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdd\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\tetb.')))

            # '[[datetime.datetime(2012, 1, 1, 0, 0) datetime.datetime(2012, 12, 31, 0, 0)]\n [datetime.datetime(2013, 1, 1, 0, 0) datetime.datetime(2013, 12, 31, 0, 0)]]'
            self.assertNumpyAll(tg.bounds.masked_value, np.ma.array(np.loads(
                '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01K\x02K\x02\x86cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdc\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdc\x0c\x1f\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07\xdd\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07\xdd\x0c\x1f\x00\x00\x00\x00\x00\x00\x85Rq\x0betb.')))

            # '[datetime.datetime(2013, 1, 1, 0, 0) datetime.datetime(2013, 1, 2, 0, 0)\n datetime.datetime(2013, 1, 3, 0, 0) datetime.datetime(2013, 1, 4, 0, 0)\n datetime.datetime(2013, 1, 5, 0, 0) datetime.datetime(2013, 1, 6, 0, 0)\n datetime.datetime(2013, 1, 7, 0, 0) datetime.datetime(2013, 1, 8, 0, 0)\n datetime.datetime(2013, 1, 9, 0, 0) datetime.datetime(2013, 1, 10, 0, 0)\n datetime.datetime(2013, 1, 11, 0, 0) datetime.datetime(2013, 1, 12, 0, 0)\n datetime.datetime(2013, 1, 13, 0, 0) datetime.datetime(2013, 1, 14, 0, 0)\n datetime.datetime(2013, 1, 15, 0, 0) datetime.datetime(2013, 1, 16, 0, 0)\n datetime.datetime(2013, 1, 17, 0, 0) datetime.datetime(2013, 1, 18, 0, 0)\n datetime.datetime(2013, 1, 19, 0, 0) datetime.datetime(2013, 1, 20, 0, 0)\n datetime.datetime(2013, 1, 21, 0, 0) datetime.datetime(2013, 1, 22, 0, 0)\n datetime.datetime(2013, 1, 23, 0, 0) datetime.datetime(2013, 1, 24, 0, 0)\n datetime.datetime(2013, 1, 25, 0, 0) datetime.datetime(2013, 1, 26, 0, 0)\n datetime.datetime(2013, 1, 27, 0, 0) datetime.datetime(2013, 1, 28, 0, 0)\n datetime.datetime(2013, 1, 29, 0, 0) datetime.datetime(2013, 1, 30, 0, 0)\n datetime.datetime(2013, 1, 31, 0, 0) datetime.datetime(2013, 2, 1, 0, 0)\n datetime.datetime(2013, 2, 2, 0, 0) datetime.datetime(2013, 2, 3, 0, 0)\n datetime.datetime(2013, 2, 4, 0, 0) datetime.datetime(2013, 2, 5, 0, 0)\n datetime.datetime(2013, 2, 6, 0, 0) datetime.datetime(2013, 2, 7, 0, 0)\n datetime.datetime(2013, 2, 8, 0, 0) datetime.datetime(2013, 2, 9, 0, 0)\n datetime.datetime(2013, 2, 10, 0, 0) datetime.datetime(2013, 2, 11, 0, 0)\n datetime.datetime(2013, 2, 12, 0, 0) datetime.datetime(2013, 2, 13, 0, 0)\n datetime.datetime(2013, 2, 14, 0, 0) datetime.datetime(2013, 2, 15, 0, 0)\n datetime.datetime(2013, 2, 16, 0, 0) datetime.datetime(2013, 2, 17, 0, 0)\n datetime.datetime(2013, 2, 18, 0, 0) datetime.datetime(2013, 2, 19, 0, 0)\n datetime.datetime(2013, 2, 20, 0, 0) datetime.datetime(2013, 2, 21, 0, 0)\n datetime.datetime(2013, 2, 22, 0, 0) datetime.datetime(2013, 2, 23, 0, 0)\n datetime.datetime(2013, 2, 24, 0, 0) datetime.datetime(2013, 2, 25, 0, 0)\n datetime.datetime(2013, 2, 26, 0, 0) datetime.datetime(2013, 2, 27, 0, 0)\n datetime.datetime(2013, 2, 28, 0, 0) datetime.datetime(2013, 12, 1, 0, 0)\n datetime.datetime(2013, 12, 2, 0, 0) datetime.datetime(2013, 12, 3, 0, 0)\n datetime.datetime(2013, 12, 4, 0, 0) datetime.datetime(2013, 12, 5, 0, 0)\n datetime.datetime(2013, 12, 6, 0, 0) datetime.datetime(2013, 12, 7, 0, 0)\n datetime.datetime(2013, 12, 8, 0, 0) datetime.datetime(2013, 12, 9, 0, 0)\n datetime.datetime(2013, 12, 10, 0, 0)\n datetime.datetime(2013, 12, 11, 0, 0)\n datetime.datetime(2013, 12, 12, 0, 0)\n datetime.datetime(2013, 12, 13, 0, 0)\n datetime.datetime(2013, 12, 14, 0, 0)\n datetime.datetime(2013, 12, 15, 0, 0)\n datetime.datetime(2013, 12, 16, 0, 0)\n datetime.datetime(2013, 12, 17, 0, 0)\n datetime.datetime(2013, 12, 18, 0, 0)\n datetime.datetime(2013, 12, 19, 0, 0)\n datetime.datetime(2013, 12, 20, 0, 0)\n datetime.datetime(2013, 12, 21, 0, 0)\n datetime.datetime(2013, 12, 22, 0, 0)\n datetime.datetime(2013, 12, 23, 0, 0)\n datetime.datetime(2013, 12, 24, 0, 0)\n datetime.datetime(2013, 12, 25, 0, 0)\n datetime.datetime(2013, 12, 26, 0, 0)\n datetime.datetime(2013, 12, 27, 0, 0)\n datetime.datetime(2013, 12, 28, 0, 0)\n datetime.datetime(2013, 12, 29, 0, 0)\n datetime.datetime(2013, 12, 30, 0, 0)\n datetime.datetime(2013, 12, 31, 0, 0)]'
            self.assertNumpyAll(td.masked_value[tg.dgroups[1]], np.ma.array(np.loads(
                '\x80\x02cnumpy.core.multiarray\n_reconstruct\nq\x01cnumpy\nndarray\nq\x02K\x00\x85U\x01b\x87Rq\x03(K\x01KZ\x85cnumpy\ndtype\nq\x04U\x02O8K\x00K\x01\x87Rq\x05(K\x03U\x01|NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?tb\x89]q\x06(cdatetime\ndatetime\nq\x07U\n\x07\xdd\x01\x01\x00\x00\x00\x00\x00\x00\x85Rq\x08h\x07U\n\x07\xdd\x01\x02\x00\x00\x00\x00\x00\x00\x85Rq\th\x07U\n\x07\xdd\x01\x03\x00\x00\x00\x00\x00\x00\x85Rq\nh\x07U\n\x07\xdd\x01\x04\x00\x00\x00\x00\x00\x00\x85Rq\x0bh\x07U\n\x07\xdd\x01\x05\x00\x00\x00\x00\x00\x00\x85Rq\x0ch\x07U\n\x07\xdd\x01\x06\x00\x00\x00\x00\x00\x00\x85Rq\rh\x07U\n\x07\xdd\x01\x07\x00\x00\x00\x00\x00\x00\x85Rq\x0eh\x07U\n\x07\xdd\x01\x08\x00\x00\x00\x00\x00\x00\x85Rq\x0fh\x07U\n\x07\xdd\x01\t\x00\x00\x00\x00\x00\x00\x85Rq\x10h\x07U\n\x07\xdd\x01\n\x00\x00\x00\x00\x00\x00\x85Rq\x11h\x07U\n\x07\xdd\x01\x0b\x00\x00\x00\x00\x00\x00\x85Rq\x12h\x07U\n\x07\xdd\x01\x0c\x00\x00\x00\x00\x00\x00\x85Rq\x13h\x07U\n\x07\xdd\x01\r\x00\x00\x00\x00\x00\x00\x85Rq\x14h\x07U\n\x07\xdd\x01\x0e\x00\x00\x00\x00\x00\x00\x85Rq\x15h\x07U\n\x07\xdd\x01\x0f\x00\x00\x00\x00\x00\x00\x85Rq\x16h\x07U\n\x07\xdd\x01\x10\x00\x00\x00\x00\x00\x00\x85Rq\x17h\x07U\n\x07\xdd\x01\x11\x00\x00\x00\x00\x00\x00\x85Rq\x18h\x07U\n\x07\xdd\x01\x12\x00\x00\x00\x00\x00\x00\x85Rq\x19h\x07U\n\x07\xdd\x01\x13\x00\x00\x00\x00\x00\x00\x85Rq\x1ah\x07U\n\x07\xdd\x01\x14\x00\x00\x00\x00\x00\x00\x85Rq\x1bh\x07U\n\x07\xdd\x01\x15\x00\x00\x00\x00\x00\x00\x85Rq\x1ch\x07U\n\x07\xdd\x01\x16\x00\x00\x00\x00\x00\x00\x85Rq\x1dh\x07U\n\x07\xdd\x01\x17\x00\x00\x00\x00\x00\x00\x85Rq\x1eh\x07U\n\x07\xdd\x01\x18\x00\x00\x00\x00\x00\x00\x85Rq\x1fh\x07U\n\x07\xdd\x01\x19\x00\x00\x00\x00\x00\x00\x85Rq h\x07U\n\x07\xdd\x01\x1a\x00\x00\x00\x00\x00\x00\x85Rq!h\x07U\n\x07\xdd\x01\x1b\x00\x00\x00\x00\x00\x00\x85Rq"h\x07U\n\x07\xdd\x01\x1c\x00\x00\x00\x00\x00\x00\x85Rq#h\x07U\n\x07\xdd\x01\x1d\x00\x00\x00\x00\x00\x00\x85Rq$h\x07U\n\x07\xdd\x01\x1e\x00\x00\x00\x00\x00\x00\x85Rq%h\x07U\n\x07\xdd\x01\x1f\x00\x00\x00\x00\x00\x00\x85Rq&h\x07U\n\x07\xdd\x02\x01\x00\x00\x00\x00\x00\x00\x85Rq\'h\x07U\n\x07\xdd\x02\x02\x00\x00\x00\x00\x00\x00\x85Rq(h\x07U\n\x07\xdd\x02\x03\x00\x00\x00\x00\x00\x00\x85Rq)h\x07U\n\x07\xdd\x02\x04\x00\x00\x00\x00\x00\x00\x85Rq*h\x07U\n\x07\xdd\x02\x05\x00\x00\x00\x00\x00\x00\x85Rq+h\x07U\n\x07\xdd\x02\x06\x00\x00\x00\x00\x00\x00\x85Rq,h\x07U\n\x07\xdd\x02\x07\x00\x00\x00\x00\x00\x00\x85Rq-h\x07U\n\x07\xdd\x02\x08\x00\x00\x00\x00\x00\x00\x85Rq.h\x07U\n\x07\xdd\x02\t\x00\x00\x00\x00\x00\x00\x85Rq/h\x07U\n\x07\xdd\x02\n\x00\x00\x00\x00\x00\x00\x85Rq0h\x07U\n\x07\xdd\x02\x0b\x00\x00\x00\x00\x00\x00\x85Rq1h\x07U\n\x07\xdd\x02\x0c\x00\x00\x00\x00\x00\x00\x85Rq2h\x07U\n\x07\xdd\x02\r\x00\x00\x00\x00\x00\x00\x85Rq3h\x07U\n\x07\xdd\x02\x0e\x00\x00\x00\x00\x00\x00\x85Rq4h\x07U\n\x07\xdd\x02\x0f\x00\x00\x00\x00\x00\x00\x85Rq5h\x07U\n\x07\xdd\x02\x10\x00\x00\x00\x00\x00\x00\x85Rq6h\x07U\n\x07\xdd\x02\x11\x00\x00\x00\x00\x00\x00\x85Rq7h\x07U\n\x07\xdd\x02\x12\x00\x00\x00\x00\x00\x00\x85Rq8h\x07U\n\x07\xdd\x02\x13\x00\x00\x00\x00\x00\x00\x85Rq9h\x07U\n\x07\xdd\x02\x14\x00\x00\x00\x00\x00\x00\x85Rq:h\x07U\n\x07\xdd\x02\x15\x00\x00\x00\x00\x00\x00\x85Rq;h\x07U\n\x07\xdd\x02\x16\x00\x00\x00\x00\x00\x00\x85Rq<h\x07U\n\x07\xdd\x02\x17\x00\x00\x00\x00\x00\x00\x85Rq=h\x07U\n\x07\xdd\x02\x18\x00\x00\x00\x00\x00\x00\x85Rq>h\x07U\n\x07\xdd\x02\x19\x00\x00\x00\x00\x00\x00\x85Rq?h\x07U\n\x07\xdd\x02\x1a\x00\x00\x00\x00\x00\x00\x85Rq@h\x07U\n\x07\xdd\x02\x1b\x00\x00\x00\x00\x00\x00\x85RqAh\x07U\n\x07\xdd\x02\x1c\x00\x00\x00\x00\x00\x00\x85RqBh\x07U\n\x07\xdd\x0c\x01\x00\x00\x00\x00\x00\x00\x85RqCh\x07U\n\x07\xdd\x0c\x02\x00\x00\x00\x00\x00\x00\x85RqDh\x07U\n\x07\xdd\x0c\x03\x00\x00\x00\x00\x00\x00\x85RqEh\x07U\n\x07\xdd\x0c\x04\x00\x00\x00\x00\x00\x00\x85RqFh\x07U\n\x07\xdd\x0c\x05\x00\x00\x00\x00\x00\x00\x85RqGh\x07U\n\x07\xdd\x0c\x06\x00\x00\x00\x00\x00\x00\x85RqHh\x07U\n\x07\xdd\x0c\x07\x00\x00\x00\x00\x00\x00\x85RqIh\x07U\n\x07\xdd\x0c\x08\x00\x00\x00\x00\x00\x00\x85RqJh\x07U\n\x07\xdd\x0c\t\x00\x00\x00\x00\x00\x00\x85RqKh\x07U\n\x07\xdd\x0c\n\x00\x00\x00\x00\x00\x00\x85RqLh\x07U\n\x07\xdd\x0c\x0b\x00\x00\x00\x00\x00\x00\x85RqMh\x07U\n\x07\xdd\x0c\x0c\x00\x00\x00\x00\x00\x00\x85RqNh\x07U\n\x07\xdd\x0c\r\x00\x00\x00\x00\x00\x00\x85RqOh\x07U\n\x07\xdd\x0c\x0e\x00\x00\x00\x00\x00\x00\x85RqPh\x07U\n\x07\xdd\x0c\x0f\x00\x00\x00\x00\x00\x00\x85RqQh\x07U\n\x07\xdd\x0c\x10\x00\x00\x00\x00\x00\x00\x85RqRh\x07U\n\x07\xdd\x0c\x11\x00\x00\x00\x00\x00\x00\x85RqSh\x07U\n\x07\xdd\x0c\x12\x00\x00\x00\x00\x00\x00\x85RqTh\x07U\n\x07\xdd\x0c\x13\x00\x00\x00\x00\x00\x00\x85RqUh\x07U\n\x07\xdd\x0c\x14\x00\x00\x00\x00\x00\x00\x85RqVh\x07U\n\x07\xdd\x0c\x15\x00\x00\x00\x00\x00\x00\x85RqWh\x07U\n\x07\xdd\x0c\x16\x00\x00\x00\x00\x00\x00\x85RqXh\x07U\n\x07\xdd\x0c\x17\x00\x00\x00\x00\x00\x00\x85RqYh\x07U\n\x07\xdd\x0c\x18\x00\x00\x00\x00\x00\x00\x85RqZh\x07U\n\x07\xdd\x0c\x19\x00\x00\x00\x00\x00\x00\x85Rq[h\x07U\n\x07\xdd\x0c\x1a\x00\x00\x00\x00\x00\x00\x85Rq\\h\x07U\n\x07\xdd\x0c\x1b\x00\x00\x00\x00\x00\x00\x85Rq]h\x07U\n\x07\xdd\x0c\x1c\x00\x00\x00\x00\x00\x00\x85Rq^h\x07U\n\x07\xdd\x0c\x1d\x00\x00\x00\x00\x00\x00\x85Rq_h\x07U\n\x07\xdd\x0c\x1e\x00\x00\x00\x00\x00\x00\x85Rq`h\x07U\n\x07\xdd\x0c\x1f\x00\x00\x00\x00\x00\x00\x85Rqaetb.')))

    def test_get_report(self):
        raise SkipTest
        keywords = dict(value=[[1000, 2000], [1000]],
                        format_time=[True, False])
        for k in self.iter_product_keywords(keywords):
            tdim = TemporalVariable(**k._asdict())
            actual = tdim.get_report()
            self.assertEqual(len(actual), 9)

        # test months in time units
        units = 'months since 1979-1-1 0'
        value = np.arange(0, 120)
        tdim = TemporalVariable(units=units, value=value)
        target = tdim.get_report()
        self.assertTrue(len(target) > 5)

    def test_get_subset_by_function(self):

        def _func_(value, bounds=None):
            months = [6, 7]
            indices = []
            for ii, dt in enumerate(value.flat):
                if dt.month in months:
                    if dt.month == 6 and dt.day >= 15:
                        indices.append(ii)
                    elif dt.month == 7 and dt.day <= 15:
                        indices.append(ii)
            return indices

        dates = get_date_list(dt(2002, 1, 31), dt(2003, 12, 31), 1)
        td = TemporalVariable(value=dates)

        ret = td.get_subset_by_function(_func_)
        self.assertEqual(ret.shape, (62,))
        for v in ret.value_datetime:
            self.assertIn(v.month, [6, 7])

        ret2 = td.get_subset_by_function(_func_, return_indices=True)
        self.assertNumpyAll(td[ret2[1]].value_datetime, ret.value_datetime)

    def test_get_time_region_value_only(self):
        dates = get_date_list(dt(2002, 1, 31), dt(2009, 12, 31), 1)
        td = TemporalVariable(value=dates)

        ret, indices = td.get_time_region({'month': [8]}, return_indices=True)
        self.assertEqual(set([8]), set([d.month for d in ret.value.flat]))

        ret, indices = td.get_time_region({'year': [2008, 2004]}, return_indices=True)
        self.assertEqual(set([2008, 2004]), set([d.year for d in ret.value.flat]))

        ret, indices = td.get_time_region({'day': [20, 31]}, return_indices=True)
        self.assertEqual(set([20, 31]), set([d.day for d in ret.value.flat]))

        ret, indices = td.get_time_region({'day': [20, 31], 'month': [9, 10], 'year': [2003]}, return_indices=True)
        self.assertNumpyAll(ret.masked_value, np.ma.array([dt(2003, 9, 20), dt(2003, 10, 20), dt(2003, 10, 31, )]))
        self.assertEqual(ret.shape, indices.shape)

        self.assertEqual(ret.extent, (datetime.datetime(2003, 9, 20), datetime.datetime(2003, 10, 31)))

    def test_get_to_conform_value(self):
        td = TemporalVariable(value=[datetime.datetime(2000, 1, 1)])
        self.assertNumpyAll(td._get_to_conform_value_(), np.ma.array([730121.]))

    def test_has_months_units(self):
        td = TemporalVariable(value=[5, 6], units='months since 1978-12')
        self.assertTrue(td._has_months_units)
        td = TemporalVariable(value=[5, 6])
        self.assertFalse(td._has_months_units)

    def test_months_in_time_units(self):
        units = "months since 1978-12"
        vec = range(0, 36)
        datetimes = get_datetime_from_months_time_units(vec, units)
        td = TemporalVariable(value=vec, units=units, calendar='standard')
        self.assertTrue(td._has_months_units)
        self.assertNumpyAll(td.value_datetime, np.ma.array(datetimes))

    def test_months_in_time_units_are_bad_netcdftime(self):
        units = "months since 1978-12"
        vec = range(0, 36)
        calendar = "standard"
        with self.assertRaises((TypeError, ValueError)):
            num2date(vec, units, calendar=calendar)

    def test_months_in_time_units_between(self):
        units = "months since 1978-12"
        vec = range(0, 36)
        datetimes = get_datetime_from_months_time_units(vec, units)
        td = TemporalVariable(value=vec, units=units, calendar='standard')
        ret = td.get_between(datetimes[0], datetimes[3])
        self.assertNumpyAll(ret.masked_value, np.ma.array([0, 1, 2, 3]))

    def test_months_not_in_time_units(self):
        units = "days since 1900-01-01"
        value = np.array([31])
        td = TemporalVariable(value=value, units=units, calendar='standard')
        self.assertFalse(td._has_months_units)

    def test_units(self):
        # Test calendar is maintained when setting units.
        td = TemporalVariable(value=[5])
        td.units = get_units_object('days since 1950-1-1', calendar='360_day')
        self.assertEqual(td.calendar, '360_day')
        self.assertEqual(td.units, 'days since 1950-1-1')

    def test_get_time_regions(self):
        dates = get_date_list(dt(2012, 1, 1), dt(2013, 12, 31), 1)

        # two simple seasons
        calc_grouping = [[6, 7, 8], [9, 10, 11]]
        time_regions = get_time_regions(calc_grouping, dates)
        correct = [[{'month': [6, 7, 8], 'year': [2012]}], [{'month': [9, 10, 11], 'year': [2012]}],
                   [{'month': [6, 7, 8], 'year': [2013]}], [{'month': [9, 10, 11], 'year': [2013]}]]
        self.assertEqual(time_regions, correct)

        # add an interannual season at the back
        calc_grouping = [[6, 7, 8], [9, 10, 11], [12, 1, 2]]
        with self.assertRaises(IncompleteSeasonError):
            get_time_regions(calc_grouping, dates)
        time_regions = get_time_regions(calc_grouping, dates, raise_if_incomplete=False)
        correct = [[{'month': [6, 7, 8], 'year': [2012]}], [{'month': [9, 10, 11], 'year': [2012]}],
                   [{'month': [12], 'year': [2012]}, {'month': [2, 1], 'year': [2013]}],
                   [{'month': [6, 7, 8], 'year': [2013]}], [{'month': [9, 10, 11], 'year': [2013]}]]
        self.assertEqual(time_regions, correct)

        # put the interannual season in the middle
        calc_grouping = [[9, 10, 11], [12, 1, 2], [6, 7, 8]]
        with self.assertRaises(IncompleteSeasonError):
            get_time_regions(calc_grouping, dates)
        time_regions = get_time_regions(calc_grouping, dates, raise_if_incomplete=False)
        correct = [[{'month': [9, 10, 11], 'year': [2012]}],
                   [{'month': [12], 'year': [2012]}, {'month': [2, 1], 'year': [2013]}],
                   [{'month': [6, 7, 8], 'year': [2012]}], [{'month': [9, 10, 11], 'year': [2013]}],
                   [{'month': [6, 7, 8], 'year': [2013]}]]
        self.assertEqual(time_regions, correct)

        # odd seasons, but covering the whole year
        calc_grouping = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
        time_regions = get_time_regions(calc_grouping, dates)
        correct = [[{'month': [1, 2, 3], 'year': [2012]}], [{'month': [4, 5, 6], 'year': [2012]}],
                   [{'month': [7, 8, 9], 'year': [2012]}], [{'month': [10, 11, 12], 'year': [2012]}],
                   [{'month': [1, 2, 3], 'year': [2013]}], [{'month': [4, 5, 6], 'year': [2013]}],
                   [{'month': [7, 8, 9], 'year': [2013]}], [{'month': [10, 11, 12], 'year': [2013]}]]
        self.assertEqual(time_regions, correct)

        # standard seasons
        calc_grouping = [[3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 1, 2]]
        time_regions = get_time_regions(calc_grouping, dates, raise_if_incomplete=False)
        correct = [[{'month': [3, 4, 5], 'year': [2012]}], [{'month': [6, 7, 8], 'year': [2012]}],
                   [{'month': [9, 10, 11], 'year': [2012]}],
                   [{'month': [12], 'year': [2012]}, {'month': [2, 1], 'year': [2013]}],
                   [{'month': [3, 4, 5], 'year': [2013]}], [{'month': [6, 7, 8], 'year': [2013]}],
                   [{'month': [9, 10, 11], 'year': [2013]}]]
        self.assertEqual(time_regions, correct)

        # in this case, the time series starts in december. the first season/year combination will not actually be
        # present in the time series and should be removed by the code.
        actual = [[{'month': [3, 4, 5], 'year': [1950]}], [{'month': [3, 4, 5], 'year': [1951]}]]
        raise_if_incomplete = False
        seasons = [[3, 4, 5]]
        dates = get_date_list(dt(1949, 12, 16), dt(1951, 12, 16), 1)
        target = get_time_regions(seasons, dates, raise_if_incomplete=raise_if_incomplete)
        self.assertEqual(actual, target)

    def test_time_range_subset(self):
        dt1 = datetime.datetime(1950, 01, 01, 12)
        dt2 = datetime.datetime(1950, 12, 31, 12)
        dates = np.array(get_date_list(dt1, dt2, 1))
        r1 = datetime.datetime(1950, 01, 01)
        r2 = datetime.datetime(1950, 12, 31)
        td = TemporalVariable(value=dates)
        ret = td.get_between(r1, r2)
        self.assertEqual(ret.value[-1], datetime.datetime(1950, 12, 30, 12, 0))
        delta = datetime.timedelta(hours=12)
        lower = dates - delta
        upper = dates + delta
        bounds = np.empty((lower.shape[0], 2), dtype=object)
        bounds[:, 0] = lower
        bounds[:, 1] = upper
        bounds = Variable(value=bounds, name='time_bounds')
        td = TemporalVariable(value=dates, bounds=bounds)
        ret = td.get_between(r1, r2)
        self.assertEqual(ret.value[-1], datetime.datetime(1950, 12, 31, 12, 0))

    def test_value_datetime_and_value_numtime(self):
        value_datetime = np.array([dt(2000, 1, 15), dt(2000, 2, 15)])
        value = date2num(value_datetime, constants.DEFAULT_TEMPORAL_UNITS, calendar=constants.DEFAULT_TEMPORAL_CALENDAR)
        keywords = dict(value=[value, value_datetime],
                        format_time=[True, False])
        for k in self.iter_product_keywords(keywords, as_namedtuple=True):
            td = TemporalVariable(**k._asdict())
            self.assertNumpyAll(td.masked_value, np.ma.array(k.value))
            try:
                self.assertNumpyAll(td.value_datetime, np.ma.array(value_datetime))
            except CannotFormatTimeError:
                self.assertFalse(k.format_time)
            self.assertNumpyAll(td.value_numtime, np.ma.array(value))

    def test_write_netcdf(self):
        tv = self.get_temporalvariable()
        path = self.get_temporary_file_path('foo.nc')
        with self.nc_scope(path, 'w') as ds:
            tv.write_netcdf(ds)
        with self.nc_scope(path) as ds:
            time = ds.variables['time']
            self.assertEqual(time.ncattrs(), ['bounds', 'calendar', 'units'])
            time_bounds = ds.variables['time_bounds']
            self.assertEqual(time_bounds.ncattrs(), ['calendar', 'units'])
        rd = RequestDataset(uri=path)
        bounds = SourcedVariable(name='time_bounds', request_dataset=rd)
        tv2 = TemporalVariable(name='time', request_dataset=rd, bounds=bounds)
        self.assertNumpyAll(tv.value_datetime, tv2.value_datetime)
        self.assertNumpyAll(tv.bounds_datetime.value, tv2.bounds_datetime.value)
        path2 = self.get_temporary_file_path('foo2.nc')
        with self.nc_scope(path2, 'w') as ds:
            tv2.write_netcdf(ds)
        self.assertNcEqual(path, path2)

    @attr('data')
    def test_write_netcdf_data(self):
        raise SkipTest('test should be removed??')
        rd = self.test_data.get_rd('cancm4_tas')
        path = os.path.join(self.current_dir_output, 'foo.nc')

        keywords = dict(with_bounds=[True, False],
                        as_datetime=[False, True])

        for k in self.iter_product_keywords(keywords, as_namedtuple=True):
            field = rd.get()
            td = field.temporal
            if not k.with_bounds:
                td.value
                td._request_dataset = None
                td.bounds = None
                self.assertIsNone(td.bounds)
            if k.as_datetime:
                td._value = td.value_datetime
                td._bounds = td.bounds_datetime

            original_value = deepcopy(td.value)
            original_bounds = deepcopy(td.bounds)

            with self.nc_scope(path, 'w') as ds:
                td.write_netcdf(ds)
                for name, expected_value in zip([td.name_value, td.name_bounds], [td.value_numtime, td.bounds_numtime]):
                    try:
                        variable = ds.variables[name]
                    except KeyError:
                        self.assertFalse(k.with_bounds)
                        continue
                    self.assertEqual(variable.calendar, td.calendar)
                    self.assertEqual(variable.units, td.units)
            self.assertNumpyAll(original_value, td.value)
            try:
                self.assertNumpyAll(original_bounds, td.bounds)
            except AttributeError:
                self.assertFalse(k.with_bounds)
                self.assertIsNone(original_bounds)


class TestTemporalGroupVariable(AbstractTestNewInterface):
    def get_tgv(self):
        rd = self.get_request_dataset()
        bounds = SourcedVariable(name='time_bnds', request_dataset=rd)
        tv = TemporalVariable(name='time', bounds=bounds, request_dataset=rd)
        return tv.get_grouping(['month'])

    @attr('data')
    def test_init(self):
        tgd = self.get_tgv()
        self.assertIsInstance(tgd, TemporalGroupVariable)

    @attr('data')
    def test_write_netcdf(self):
        tgd = self.get_tgv()
        path = os.path.join(self.current_dir_output, 'foo.nc')
        with self.nc_scope(path, 'w') as ds:
            tgd.write_netcdf(ds)
        with self.nc_scope(path) as ds:
            self.assertIn('climatology_bounds', ds.variables)
            ncvar = ds.variables[tgd.name]
            self.assertEqual(ncvar.climatology, 'climatology_bounds')
            with self.assertRaises(AttributeError):
                ncvar.bounds

        # Test failure and make sure original bounds name is preserved.
        self.assertNotEqual(tgd.bounds.name, 'climatology_bounds')
        with self.nc_scope(path, 'w') as ds:
            try:
                tgd.write_netcdf(ds, darkness='forever')
            except TypeError:
                self.assertNotEqual(tgd.bounds.name, 'climatology_bounds')
