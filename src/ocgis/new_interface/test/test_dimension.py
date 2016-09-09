import numpy as np

from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.mpi import OcgMpi, MPI_SIZE, MPI_RANK
from ocgis.new_interface.test.test_new_interface import AbstractTestNewInterface
from ocgis.test.base import attr


class TestDimension(AbstractTestNewInterface):
    @staticmethod
    def get_dimension(**kwargs):
        name = kwargs.pop('name', 'foo')
        kwargs['size'] = kwargs.get('size', 10)
        return Dimension(name, **kwargs)

    def test_init(self):
        dim = Dimension('foo')
        self.assertEqual(dim.name, 'foo')
        self.assertIsNone(dim.size)
        self.assertIsNone(dim.size_current)
        self.assertTrue(dim.is_unlimited)
        self.assertEqual(len(dim), 0)
        self.assertEqual(dim.bounds_local, (0, len(dim)))
        self.assertEqual(dim.bounds_global, dim.bounds_local)

        dim = Dimension('foo', size=23)
        self.assertEqual(dim.size, 23)

        src_idx = np.arange(0, 10, dtype=Dimension._default_dtype)
        dim = self.get_dimension(src_idx=src_idx)
        self.assertNumpyAll(dim._src_idx, src_idx)
        self.assertEqual(dim._src_idx.shape[0], 10)

        # Test distributed dimensions require and size definition.
        with self.assertRaises(ValueError):
            Dimension('foo', dist=True)

        # Test without size definition and a source index.
        for src_idx in ['auto', 'ato', [0, 1, 2]]:
            try:
                dim = Dimension('foo', src_idx=src_idx)
            except ValueError:
                self.assertNotEqual(src_idx, 'auto')
            else:
                self.assertIsNone(dim._src_idx)

    def test_bounds_local(self):
        dim = Dimension('a', 5)
        dim.bounds_local = [0, 2]
        self.assertEqual(dim.bounds_local, (0, 2))

    def test_convert_to_empty(self):
        dim = Dimension('three', 3, src_idx=[10, 11, 12])
        dim.convert_to_empty()
        self.assertFalse(dim.is_unlimited)
        self.assertTrue(dim.is_empty)

    def test_copy(self):
        sd = self.get_dimension(src_idx=np.arange(10))
        self.assertIsNotNone(sd._src_idx)
        sd2 = sd.copy()
        self.assertTrue(np.may_share_memory(sd._src_idx, sd2._src_idx))
        sd3 = sd2[2:5]
        self.assertEqual(sd, sd2)
        self.assertNotEqual(sd2, sd3)
        self.assertTrue(np.may_share_memory(sd2._src_idx, sd._src_idx))
        self.assertTrue(np.may_share_memory(sd2._src_idx, sd3._src_idx))
        self.assertTrue(np.may_share_memory(sd3._src_idx, sd._src_idx))

        # Test setting new values on object.
        dim = Dimension('five', 5)
        cdim = dim.copy()
        cdim._name = 'six'
        self.assertEqual(dim.name, 'five')
        self.assertEqual(cdim.name, 'six')

    def test_eq(self):
        lhs = self.get_dimension()
        rhs = self.get_dimension()
        self.assertEqual(lhs, rhs)

    @attr('mpi')
    def test_get_distributed_slice(self):
        for d in [True, False]:
            dist = OcgMpi()
            dim = dist.create_dimension('five', 5, dist=d, src_idx='auto')
            dist.update_dimension_bounds()
            self.assertEqual(dim.bounds_global, (0, 5))

            if dim.dist:
                if MPI_RANK > 4:
                    self.assertTrue(dim.is_empty)
                else:
                    self.assertFalse(dim.is_empty)

            sub = dim.get_distributed_slice(slice(1, 3))

            if dim.dist:
                if not dim.is_empty:
                    self.assertIsNotNone(dim._src_idx)
                else:
                    self.assertTrue(MPI_RANK + 1 >= len(dim))
                self.assertEqual(sub.bounds_global, (0, 2))

                if MPI_SIZE == 2:
                    desired_emptiness = {0: False, 1: True}[MPI_RANK]
                    desired_bounds_local = {0: (0, 2), 1: (0, 0)}[MPI_RANK]
                    self.assertEqual(sub.is_empty, desired_emptiness)
                    self.assertEqual(sub.bounds_local, desired_bounds_local)
                if MPI_SIZE >= 5 and 0 < MPI_RANK > 2:
                    self.assertTrue(sub.is_empty)
            else:
                self.assertEqual(len(dim), 5)
                self.assertEqual(dim.bounds_global, (0, 5))
                self.assertEqual(dim.bounds_local, (0, 5))

        dist = OcgMpi()
        dim = dist.create_dimension('five', 5, dist=True, src_idx='auto')
        dist.update_dimension_bounds()
        sub = dim.get_distributed_slice(slice(2, 4))
        if MPI_SIZE == 3 and MPI_RANK == 2:
            self.assertTrue(sub.is_empty)

    def test_getitem(self):
        dim = Dimension('foo', size=50)
        sub = dim[30:40]
        self.assertEqual(len(sub), 10)

        dim = Dimension('foo', size=None)
        with self.assertRaises(IndexError):
            dim[400:500]

        # Test with negative indexing.
        dim = Dimension(name='geom', size=2, src_idx='auto')
        slc = slice(0, -1, None)
        actual = dim[slc]
        self.assertEqual(actual, Dimension('geom', size=1, src_idx='auto'))

        dim = Dimension(name='geom', size=5, src_idx=np.arange(5))
        slc = slice(1, -2, None)
        actual = dim[slc]
        desired = Dimension('geom', size=2, src_idx=[1, 2])
        self.assertEqual(actual, desired)

        dim = self.get_dimension(src_idx=np.arange(10))

        sub = dim[4]
        self.assertEqual(sub.size, 1)

        sub = dim[4:5]
        self.assertEqual(sub.size, 1)

        sub = dim[4:6]
        self.assertEqual(sub.size, 2)

        sub = dim[[4, 5, 6]]
        self.assertEqual(sub.size, 3)

        sub = dim[[2, 4, 6]]
        self.assertEqual(sub.size, 3)
        self.assertNumpyAll(sub._src_idx, dim._src_idx[[2, 4, 6]])

        sub = dim[:]
        self.assertEqual(len(sub), len(dim))

        dim = self.get_dimension()
        sub = dim[2:]
        self.assertEqual(len(sub), 8)

        dim = self.get_dimension(src_idx=np.arange(10))
        sub = dim[3:-1]
        np.testing.assert_equal(sub._src_idx, [3, 4, 5, 6, 7, 8])

        dim = self.get_dimension(src_idx=np.arange(10))
        sub = dim[-3:]
        self.assertEqual(sub._src_idx.shape[0], sub.size)

        dim = self.get_dimension(src_idx=np.arange(10))
        sub = dim[-7:-3]
        self.assertEqual(sub._src_idx.shape[0], sub.size)

        dim = self.get_dimension(src_idx=np.arange(10))
        sub = dim[:-3]
        self.assertEqual(sub._src_idx.shape[0], sub.size)

        # Test source index is None after slicing.
        dim = Dimension('water', 10)
        sub = dim[0:3]
        self.assertIsNone(sub._src_idx)

    def test_len(self):
        dim = Dimension('foo')
        self.assertEqual(len(dim), 0)

        # Test size current is used for length.
        dim = Dimension('unlimited', size=None, size_current=4)
        self.assertEqual(len(dim), 4)

    def test_set_size(self):
        dim = self.get_dimension(src_idx='auto')
        kwds = {'size': [None, 0, 1, 3], 'src_idx': [None, 'auto', np.arange(3)]}
        for k in self.iter_product_keywords(kwds):
            try:
                dim.set_size(k.size, src_idx=k.src_idx)
            except ValueError:
                self.assertTrue(k.size != 3)
                self.assertIsInstance(k.src_idx, np.ndarray)
                continue
            if k.size is None:
                self.assertTrue(dim.is_unlimited)
            else:
                self.assertEqual(len(dim), k.size)
            if k.src_idx is None:
                self.assertIsNone(dim._src_idx)
            elif isinstance(k.src_idx, basestring) and k.src_idx == 'auto' and k.size is not None:
                self.assertIsNotNone(dim._src_idx)
