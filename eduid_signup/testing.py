import unittest

from eduid_signup.db import MongoDB

MONGO_URI_TEST = 'mongodb://localhost:27017/eduid_signup_test'


class DBTests(unittest.TestCase):
    """Base TestCase for those tests that need a db configured"""

    clean_collections = tuple()

    def setUp(self):
        mongodb = MongoDB(MONGO_URI_TEST)
        self.db = mongodb.get_database()

    def tearDown(self):
        for collection in self.clean_collections:
            self.db.drop_collection(collection)
