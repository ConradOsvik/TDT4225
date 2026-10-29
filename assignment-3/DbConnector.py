import os

from pymongo import MongoClient

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_NAME = os.environ.get("DB_NAME", "movies")
DB_USER = os.environ.get("DB_USER", "movies")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "movies")
# The database the user was created in. The local container's user is a root
# user in "admin"; on the VM the readWrite user lives in DB_NAME itself.
DB_AUTH_SOURCE = os.environ.get("DB_AUTH_SOURCE", "admin")


class DbConnector:
    """
    Connects to the MongoDB server on the Ubuntu virtual machine.
    Connector needs HOST, USER and PASSWORD to connect.

    Example:
    HOST = "tdt4225-00.idi.ntnu.no" // Your server IP address/domain name
    USER = "testuser" // This is the user you created and added privileges for
    PASSWORD = "test123" // The password you set for said user

    The defaults match the local container in docker-compose.yml. Set DB_HOST,
    DB_NAME, DB_USER, DB_PASSWORD and DB_AUTH_SOURCE to connect somewhere else.
    """

    def __init__(self,
                 DATABASE=DB_NAME,
                 HOST=DB_HOST,
                 USER=DB_USER,
                 PASSWORD=DB_PASSWORD,
                 AUTH_SOURCE=DB_AUTH_SOURCE):
        uri = "mongodb://%s:%s@%s/%s?authSource=%s" % (USER, PASSWORD, HOST, DATABASE, AUTH_SOURCE)
        # Connect to the databases
        try:
            self.client = MongoClient(uri)
            self.db = self.client[DATABASE]
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)
            raise

        # get database information
        print("Connected to MongoDB", self.client.server_info()["version"])
        print("You are connected to the database:", self.db.name)
        print("-----------------------------------------------\n")

    def close_connection(self):
        # close the DB connection
        self.client.close()
        print("\n-----------------------------------------------")
        print("Connection to %s-db is closed" % self.db.name)
