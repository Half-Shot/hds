import unittest
import logging
from sys import argv
from .client import ClientTestCase
from .store.redis_store import RedisStoreTestCase

if "--verbose" in argv:
    logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    unittest.main()