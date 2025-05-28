import pymysql
from config import DATABASE_CONFIG

def get_connection():
    return pymysql.connect(
        host=DATABASE_CONFIG['host'],
        user=DATABASE_CONFIG['user'],
        password=DATABASE_CONFIG['password'],
        database=DATABASE_CONFIG['database'],
        cursorclass=pymysql.cursors.DictCursor
    )
