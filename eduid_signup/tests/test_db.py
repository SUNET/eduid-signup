import unittest

from eduid_am import db


class DummyDatabase(object):

    def __init__(self, name):
        self.name = name
        self.is_authenticated = False

    def authenticate(self, user, password):
        self.is_authenticated = True


class DummyConnection(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __getitem__(self, key):
        return DummyDatabase(key)


class MongoDBTests(unittest.TestCase):

    def test_uri(self):
        # default db_uri
        mdb = db.MongoDB(connection_factory=DummyConnection)

        self.assertEqual(mdb.db_uri, db.DEFAULT_MONGODB_URI)
        self.assertEqual(mdb.database_name, db.DEFAULT_MONGODB_NAME)
        database = mdb.get_database()
        self.assertTrue(isinstance(database, DummyDatabase))
        self.assertEqual(database.name, mdb.database_name)
        self.assertFalse(database.is_authenticated)

        # full specified uri
        uri = 'mongodb://db.example.com:1111/testdb'
        mdb = db.MongoDB(uri, connection_factory=DummyConnection)
        conn = mdb.get_connection()
        database = mdb.get_database()
        self.assertEqual(mdb.db_uri, uri)
        self.assertEqual(mdb.database_name, 'testdb')
        self.assertFalse(database.is_authenticated)

        # uri without path component
        uri = 'mongodb://db.example.com:1111'
        mdb = db.MongoDB(uri, connection_factory=DummyConnection)
        conn = mdb.get_connection()
        database = mdb.get_database()
        self.assertEqual(mdb.db_uri, uri)
        self.assertEqual(mdb.database_name, db.DEFAULT_MONGODB_NAME)
        self.assertFalse(database.is_authenticated)

        # uri without port
        uri = 'mongodb://db.example.com'
        mdb = db.MongoDB(uri, connection_factory=DummyConnection)
        conn = mdb.get_connection()
        self.assertEqual(mdb.db_uri, uri)
        self.assertEqual(mdb.database_name, db.DEFAULT_MONGODB_NAME)
        self.assertFalse(database.is_authenticated)

        # uri without anything
        uri = 'mongodb://'
        mdb = db.MongoDB(uri, connection_factory=DummyConnection)
        conn = mdb.get_connection()
        database = mdb.get_database()
        self.assertEqual(mdb.db_uri, 'mongodb://')
        self.assertEqual(mdb.database_name, db.DEFAULT_MONGODB_NAME)
        self.assertFalse(database.is_authenticated)

        # uri with username and password
        uri = 'mongodb://john:secret@db.example.com:1111/testdb'
        mdb = db.MongoDB(uri, connection_factory=DummyConnection)
        conn = mdb.get_connection()
        database = mdb.get_database()
        self.assertEqual(mdb.db_uri, uri)
        self.assertEqual(mdb.database_name, 'testdb')
