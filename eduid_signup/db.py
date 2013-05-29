import pymongo

DEFAULT_MONGODB_HOST = 'localhost'
DEFAULT_MONGODB_PORT = 27017
DEFAULT_MONGODB_NAME = 'eduid'
DEFAULT_MONGODB_URI = 'mongodb://%s:%d/%s' % (DEFAULT_MONGODB_HOST,
                                              DEFAULT_MONGODB_PORT,
                                              DEFAULT_MONGODB_NAME)


class MongoDB(object):
    """Simple wrapper to get pymongo real objects from the settings uri"""

    def __init__(self, db_uri=DEFAULT_MONGODB_URI,
                 connection_factory=pymongo.MongoClient):
        self.db_uri = db_uri
        self.connection = connection_factory(
            host=self.db_uri,
            tz_aware=True)

        if self.db_uri.count("/") == 3:
            self.database_name = self.db_uri.split("/")[-1]
        else:
            self.database_name = DEFAULT_MONGODB_NAME

    def get_connection(self):
        return self.connection

    def get_database(self, database_name=None):
        if database_name is None:
            return self.connection[self.database_name]
        else:
            return self.connection[database_name]


def get_db(request):
    return request.registry.settings['mongodb'].get_database()
