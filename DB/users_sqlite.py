import sqlite3
from typing import Optional, List, Tuple, Dict, Any


class Database:
    def __init__(self, db_name: str = 'users.db'):
        """Инициализация базы данных и создание таблиц"""
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Создание таблиц users и queries"""
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            query_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query_text TEXT NOT NULL,
            query_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')

        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_queries ON queries(user_id)')
        self.conn.commit()

    def add_user(self, user_id: int, username: Optional[str] = None,
                 first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Добавление нового пользователя"""
        self.cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)''', (user_id, username, first_name, last_name))
        self.conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе"""
        self.cursor.execute('''
        SELECT user_id, username, first_name, last_name, is_admin, registration_date 
        FROM users WHERE user_id = ?''', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'is_admin': bool(row[4]),
                'registration_date': row[5]
            }
        return None

    def update_user_info(self, user_id: int, username: Optional[str] = None,
                         first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Обновление информации о пользователе"""
        current_data = self.get_user(user_id)
        if not current_data:
            return

        username = username if username is not None else current_data['username']
        first_name = first_name if first_name is not None else current_data['first_name']
        last_name = last_name if last_name is not None else current_data['last_name']

        self.cursor.execute('''
        UPDATE users 
        SET username = ?, first_name = ?, last_name = ?
        WHERE user_id = ?''', (username, first_name, last_name, user_id))
        self.conn.commit()

    def set_admin(self, user_id: int, is_admin: bool = True):
        """Назначение/снятие прав администратора"""
        self.cursor.execute('''
        UPDATE users SET is_admin = ? WHERE user_id = ?''', (int(is_admin), user_id))
        self.conn.commit()

    def delete_user(self, user_id: int):
        """Удаление пользователя и всех его запросов"""
        self.cursor.execute('DELETE FROM queries WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получение списка всех пользователей"""
        self.cursor.execute('''
        SELECT user_id, username, first_name, last_name, is_admin, registration_date 
        FROM users''')
        return [{
            'user_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'is_admin': bool(row[4]),
            'registration_date': row[5]
        } for row in self.cursor.fetchall()]

    def get_admins(self) -> List[int]:
        """Получение списка ID администраторов"""
        self.cursor.execute('SELECT user_id FROM users WHERE is_admin = 1')
        return [row[0] for row in self.cursor.fetchall()]

    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        self.cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        return bool(row[0]) if row else False

    def add_query(self, user_id: int, query_text: str):
        """Добавление нового запроса"""
        self.cursor.execute('''
        INSERT INTO queries (user_id, query_text)
        VALUES (?, ?)''', (user_id, query_text))
        self.conn.commit()

    def get_user_queries(self, user_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение запросов пользователя"""
        query = '''
        SELECT query_id, query_text, query_date 
        FROM queries 
        WHERE user_id = ?
        ORDER BY query_date DESC'''

        if limit:
            query += ' LIMIT ?'
            self.cursor.execute(query, (user_id, limit))
        else:
            self.cursor.execute(query, (user_id,))

        return [{
            'query_id': row[0],
            'query_text': row[1],
            'query_date': row[2]
        } for row in self.cursor.fetchall()]

    def get_all_queries(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение всех запросов всех пользователей"""
        query = '''
        SELECT q.query_id, q.user_id, u.username, q.query_text, q.query_date 
        FROM queries q
        LEFT JOIN users u ON q.user_id = u.user_id
        ORDER BY q.query_date DESC'''

        if limit:
            query += ' LIMIT ?'
            self.cursor.execute(query, (limit,))
        else:
            self.cursor.execute(query)

        return [{
            'query_id': row[0],
            'user_id': row[1],
            'username': row[2],
            'query_text': row[3],
            'query_date': row[4]
        } for row in self.cursor.fetchall()]

    def delete_query(self, query_id: int):
        """Удаление конкретного запроса"""
        self.cursor.execute('DELETE FROM queries WHERE query_id = ?', (query_id,))
        self.conn.commit()

    def delete_all_user_queries(self, user_id: int):
        """Удаление всех запросов пользователя"""
        self.cursor.execute('DELETE FROM queries WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def close(self):
        """Закрытие соединения с базой данных"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    with Database() as db:
        db.add_user(123456789, username='legend', first_name='sergey', last_name='litvinov')
        db.add_user(987654321, username='pidor', first_name='vova')

        db.set_admin(123456789, True)

        db.add_query(123456789, 'random movie')
        db.add_query(987654321, 'горбатая гора')
        db.add_query(123456789, 'порно')

        print("Админы:", db.get_admins())
        print("Запросы пользователя 123456789:", db.get_user_queries(123456789))
        print("Все запросы:", db.get_all_queries(limit=2))

        queries = db.get_user_queries(123456789)
        if queries:
            db.delete_query(queries[0]['query_id'])

        db.delete_user(987654321)
