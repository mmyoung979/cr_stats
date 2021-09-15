# Python imports
from unittest import TestCase


class TestSanity(TestCase):
    def test_sanity(self):
        self.assertEqual(1 + 1, 2)
        assert True != False
