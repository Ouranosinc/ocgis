import numpy as np

from ocgis.new_interface.dimension import Dimension
from ocgis.new_interface.mpi import MPI_SIZE, MPI_RANK
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

        dim = Dimension('foo', size=23)
        self.assertEqual(dim.size, 23)

        src_idx = np.arange(0, 10, dtype=Dimension._default_dtype)
        dim = self.get_dimension(src_idx=src_idx)
        self.assertNumpyAll(dim._src_idx, src_idx)
        self.assertEqual(dim._src_idx.shape[0], 10)

    @attr('mpi-2', 'mpi-5', 'mpi-8')
    def test_init_mpi(self):
        kwds = {'dist': [True, False], 'src_idx': [None, [10, 20, 30, 40, 50]]}
        for k in self.iter_product_keywords(kwds):
            dim = Dimension('the_d', 5, src_idx=k.src_idx, dist=k.dist)
            self.assertEqual(dim.mpi.size_global, 5)
            self.assertEqual(dim.mpi.bounds_global, (0, 5))
            if MPI_SIZE == 1:
                self.assertEqual(dim.mpi.bounds_local, (0, 5))
            if k.dist:
                if MPI_SIZE == 5:
                    bounds = dim.mpi.bounds_local
                    self.assertEqual(bounds[1] - bounds[0], 1)
                elif MPI_SIZE == 8:
                    self.log.debug('dim._src_idx {}'.format(dim._src_idx))
                    if MPI_RANK > 4:
                        self.assertIsNone(dim._src_idx)
                    else:
                        self.assertEqual(len(dim._src_idx), 1)
            else:
                self.assertEqual(dim.mpi.bounds_local, dim.mpi.bounds_global)

        # Test with zero length.
        dim = Dimension('zero', size=0, dist=True)
        self.assertEqual(len(dim), 0)
        self.assertIsNone(dim._src_idx)

        # Test unlimited dimension.
        dim = Dimension('unlimited', size=None, dist=True, src_idx=[3, 4, 5, 6])
        self.assertEqual(dim.mpi.size_global, 4)
        if MPI_SIZE == 2:
            self.assertEqual(len(dim), 2)
            if MPI_RANK == 0:
                self.assertEqual(dim._src_idx.tolist(), [3, 4])
            elif MPI_RANK == 1:
                self.assertEqual(dim._src_idx.tolist(), [5, 6])
            else:
                self.assertIsNone(dim._src_idx)
        elif MPI_SIZE == 1:
            self.assertIsNotNone(dim._src_idx)

        # Test some length designation is needed for an unlimited dimension in the distributed case.
        with self.assertRaises(ValueError):
            Dimension('ua', dist=True)

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

    def test_eq(self):
        lhs = self.get_dimension()
        rhs = self.get_dimension()
        self.assertEqual(lhs, rhs)

    def test_getitem(self):
        dim = Dimension('foo', size=50)
        sub = dim[30:40]
        self.assertEqual(len(sub), 10)

        dim = Dimension('foo', size=None)
        with self.assertRaises(IndexError):
            dim[400:500]

        # Test with negative indexing.
        dim = Dimension(name='geom', size=2)
        slc = slice(0, -1, None)
        actual = dim[slc]
        self.assertEqual(actual, Dimension('geom', size=1))

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

    def test_len(self):
        dim = Dimension('foo')
        self.assertEqual(len(dim), 0)

        # Test size current is used for length.
        dim = Dimension('unlimited', size=None, size_current=4)
        self.assertEqual(len(dim), 4)

    @attr('mpi-2')
    def test_scatter(self):
        d = Dimension('scatter', 6, dist=False)
        self.assertEqual(len(d._src_idx), 6)
        ds = d.scatter()
        if MPI_SIZE == 2:
            llb, lub = ds.mpi.bounds_local
            self.assertEqual(lub - llb, 3)
            self.assertEqual(len(ds._src_idx), 3)
