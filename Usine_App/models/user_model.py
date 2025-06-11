from flask_login import UserMixin
from db import get_connection

class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

    @staticmethod
    def get_by_username(login):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE login = %s", (login,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return User(user['id'], user['login'], user['password'], user['role'])
        return None

    @staticmethod
    def get_by_username_and_role(username, role):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE login = %s AND role = %s", (username, role))
        user = cursor.fetchone()
        conn.close()
        if user:
            return User(user['id'], user['login'], user['password'], user['role'])
        return None

    def check_password(self, password):
       
        return self.password == password
