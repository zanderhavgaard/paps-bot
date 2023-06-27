"""
Database related functions for use with paps-bot
"""

import os
import sys
import logging
import psycopg2
from psycopg2 import sql

# get the bot logger
logger = logging.getLogger("discord")


def create_db_connection_string_from_env_vars() -> str:
    """read environment variables and build libpq connection string"""
    # read each env var and check that it gets a value, otherwise print a message to user and exit
    db_host = os.getenv("DB_HOST", None)
    if not db_host:
        print("ERROR: 'DB_HOST' env var not set.")
        sys.exit(1)

    db_name = os.getenv("DB_NAME", None)
    if not db_name:
        print("ERROR: 'DB_NAME' env var not set.")
        sys.exit(1)

    db_user = os.getenv("DB_USER", None)
    if not db_user:
        print("ERROR: 'DB_USER' env var not set.")
        sys.exit(1)

    db_password = os.getenv("DB_PASSWORD", None)
    if not db_password:
        print("ERROR: 'DB_PASSWORD' env var not set.")
        sys.exit(1)

    db_port = os.getenv("DB_PORT", None)
    if not db_port:
        print("ERROR: 'DB_PORT' env var not set.")
        sys.exit(1)

    connection_string = f"host={db_host} port={db_port} user={db_user} password={db_password} dbname={db_name}"
    print(connection_string)
    return connection_string


DB_CONNECTION_STRING = create_db_connection_string_from_env_vars()


def create_connection():
    """Function establishing connection to database"""
    conn = None
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
    except psycopg2.DatabaseError as err:
        print(err)
    return conn


def create_table_sql():
    """
    Function creating a blank table, if it does not already exist, in postgreSQL
    """
    conn = create_connection()
    cur = conn.cursor()
    table_name = "paps_table"
    sql_table_query = sql.SQL(
        f"""CREATE TABLE IF NOT EXISTS {table_name} (
        game_id SERIAL PRIMARY KEY,
        game_type VARCHAR(255) NOT NULL,
        game_date DATE NOT NULL,
        game_time TIME NOT NULL
        )
        """
    )
    try:
        cur.execute(sql_table_query)
        conn.commit()
        cur.close()
        conn.close()
    except psycopg2.Error as err:
        logger.error("Error creating table: %s", str(err))
