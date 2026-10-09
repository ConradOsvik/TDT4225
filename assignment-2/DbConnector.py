import os

import mysql.connector as mysql

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_NAME = os.environ.get("DB_NAME", "porto")
DB_USER = os.environ.get("DB_USER", "porto")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "porto")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))


class DbConnector:
    """
    Connects to the MySQL server on the Ubuntu virtual machine.
    Connector needs HOST, DATABASE, USER and PASSWORD to connect,
    while PORT is optional and should be 3306.

    Example:
    HOST = "tdt4225-00.idi.ntnu.no" // Your server IP address/domain name
    DATABASE = "testdb" // Database name, if you just want to connect to MySQL server, leave it empty
    USER = "testuser" // This is the user you created and added privileges for
    PASSWORD = "test123" // The password you set for said user

    The defaults match the local container in docker-compose.yml. Set DB_HOST,
    DB_NAME, DB_USER, DB_PASSWORD and DB_PORT to connect somewhere else.
    """

    def __init__(self,
                 HOST=DB_HOST,
                 DATABASE=DB_NAME,
                 USER=DB_USER,
                 PASSWORD=DB_PASSWORD,
                 PORT=DB_PORT):
        # Connect to the database
        try:
            # allow_local_infile lets insert_data.py use LOAD DATA LOCAL INFILE.
            connection = mysql.connect(host=HOST, database=DATABASE, user=USER, password=PASSWORD, port=PORT,
                                       allow_local_infile=True)
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)
            raise
        # The connector's type hints allow None here; it never is at runtime.
        assert connection is not None
        self.db_connection = connection

        # Get the db cursor
        self.cursor = self.db_connection.cursor()

        print("Connected to:", self.db_connection.get_server_info())
        # get database information
        self.cursor.execute("select database();")
        database_name = self.cursor.fetchone()
        print("You are connected to the database:", database_name)
        print("-----------------------------------------------\n")

    def close_connection(self):
        # close the cursor
        self.cursor.close()
        # close the DB connection
        self.db_connection.close()
        print("\n-----------------------------------------------")
        print("Connection to %s is closed" % self.db_connection.get_server_info())
