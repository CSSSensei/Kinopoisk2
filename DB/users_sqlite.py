import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional, Iterator
from config_data.models import User, Query


class Database:
    def __init__(self, db_name: str = f'{os.path.dirname(__file__)}/users.db'):
        """Инициализация базы данных и создание таблиц"""
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
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

    def add_user(self, user: User) -> User:
        """Добавляет или обновляет пользователя"""
        existing_user = self.get_user(user.user_id)

        if existing_user:
            needs_update = (
                    (existing_user.username != user.username)
                    or (existing_user.first_name != user.first_name)
                    or (existing_user.last_name != user.last_name)
            )

            if needs_update:
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?
                    WHERE user_id = ?''',
                                    (user.username, user.first_name, user.last_name, user.user_id))
                self.conn.commit()
        else:
            self.cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, is_admin)
                VALUES (?, ?, ?, ?, ?)''',
                                (user.user_id, user.username, user.first_name, user.last_name, int(user.is_admin)))
            self.conn.commit()

        return self.get_user(user.user_id)

    def get_user(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        self.cursor.execute('''
        SELECT user_id, username, first_name, last_name, is_admin, registration_date 
        FROM users WHERE user_id = ?''', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin']),
                registration_date=(
                        datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                        if row['registration_date']
                        else None
                    )
            )
        return None

    def update_user(self, user: User) -> Optional[User]:
        """Обновление информации о пользователе"""
        self.cursor.execute('''
        UPDATE users 
        SET username = ?, first_name = ?, last_name = ?, is_admin = ?
        WHERE user_id = ?''',
                            (user.username, user.first_name, user.last_name, int(user.is_admin), user.user_id))
        self.conn.commit()
        return self.get_user(user.user_id)

    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя и всех его запросов"""
        self.cursor.execute('DELETE FROM queries WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_all_users(self) -> Iterator[User]:
        """Генератор всех пользователей"""
        self.cursor.execute('''
        SELECT user_id, username, first_name, last_name, is_admin, registration_date 
        FROM users ORDER BY registration_date DESC''')
        for row in self.cursor:
            yield User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin']),
                registration_date=(
                        datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                        if row['registration_date']
                        else None
                    )
            )

    def get_last_queries(self, amount: int = 10) -> List[Query]:
        """
        Возвращает последние N запросов из базы данных
        """
        if amount < 0:
            raise ValueError("Amount cannot be negative")

        try:
            self.cursor.execute('''
                SELECT q.query_id, q.user_id, q.query_text, q.query_date,
                       u.username, u.first_name, u.last_name, u.is_admin
                FROM queries q
                LEFT JOIN users u ON q.user_id = u.user_id
                ORDER BY q.query_date DESC
                LIMIT ?
            ''', (amount,))

            queries = []
            for row in self.cursor.fetchall():
                user = User(
                    user_id=row['user_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    is_admin=bool(row['is_admin'])
                ) if row['user_id'] else None

                query = Query(
                    query_id=row['query_id'],
                    user_id=row['user_id'],
                    query_text=row['query_text'],
                    query_date=(
                        datetime.fromisoformat(row['query_date']) + timedelta(hours=3)
                        if row['query_date']
                        else None
                    ),
                    user=user
                )
                queries.append(query)

            return queries

        except sqlite3.Error as e:
            print(f"Database error in get_last_queries: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_last_queries: {e}")
            return []

    def get_admins(self) -> Iterator[User]:
        """Генератор администраторов"""
        self.cursor.execute('''
        SELECT user_id, username, first_name, last_name, is_admin, registration_date 
        FROM users WHERE is_admin = 1''')
        for row in self.cursor:
            yield User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=True,
                registration_date=(
                        datetime.fromisoformat(row['registration_date']) + timedelta(hours=3)
                        if row['registration_date']
                        else None
                    )
            )

    def add_query(self, query: Query) -> Query:
        """Добавление нового запроса"""
        self.cursor.execute('''
        INSERT INTO queries (user_id, query_text)
        VALUES (?, ?)''', (query.user_id, query.query_text))
        query_id = self.cursor.lastrowid
        self.conn.commit()
        return self.get_query(query_id)

    def get_query(self, query_id: int) -> Optional[Query]:
        """Получение запроса по ID"""
        self.cursor.execute('''
        SELECT q.query_id, q.user_id, q.query_text, q.query_date,
               u.username, u.first_name, u.last_name, u.is_admin
        FROM queries q
        LEFT JOIN users u ON q.user_id = u.user_id
        WHERE q.query_id = ?''', (query_id,))
        row = self.cursor.fetchone()
        if row:
            user = User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin'])
            ) if row['user_id'] else None

            return Query(
                query_id=row['query_id'],
                user_id=row['user_id'],
                query_text=row['query_text'],
                query_date=(
                        datetime.fromisoformat(row['query_date']) + timedelta(hours=3)
                        if row['query_date']
                        else None
                    ),
                user=user
            )
        return None

    def get_user_queries(self, user_id: int, limit: Optional[int] = None) -> Iterator[Query]:
        """Генератор запросов пользователя"""
        query = '''
        SELECT q.query_id, q.user_id, q.query_text, q.query_date,
               u.username, u.first_name, u.last_name, u.is_admin
        FROM queries q
        LEFT JOIN users u ON q.user_id = u.user_id
        WHERE q.user_id = ?
        ORDER BY q.query_date DESC'''

        params = (user_id,)
        if limit:
            query += ' LIMIT ?'
            params = (user_id, limit)

        self.cursor.execute(query, params)
        for row in self.cursor:
            user = User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin'])
            )

            yield Query(
                query_id=row['query_id'],
                user_id=row['user_id'],
                query_text=row['query_text'],
                query_date=(
                        datetime.fromisoformat(row['query_date']) + timedelta(hours=3)
                        if row['query_date']
                        else None
                    ),
                user=user
            )

    def get_all_queries(self, limit: Optional[int] = None) -> Iterator[Query]:
        """Генератор всех запросов"""
        query = '''
        SELECT q.query_id, q.user_id, q.query_text, q.query_date,
               u.username, u.first_name, u.last_name, u.is_admin
        FROM queries q
        LEFT JOIN users u ON q.user_id = u.user_id
        ORDER BY q.query_date DESC'''

        params = ()
        if limit:
            query += ' LIMIT ?'
            params = (limit,)

        self.cursor.execute(query, params)
        for row in self.cursor:
            user = User(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin'])
            ) if row['user_id'] else None

            yield Query(
                query_id=row['query_id'],
                user_id=row['user_id'],
                query_text=row['query_text'],
                query_date=(
                        datetime.fromisoformat(row['query_date']) + timedelta(hours=3)
                        if row['query_date']
                        else None
                    ),
                user=user
            )

    def set_admin(self, user_id: int, is_admin: bool = True) -> bool:
        """
        Устанавливает или снимает права администратора у пользователя
        """
        try:
            # Проверяем существование пользователя
            self.cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            if not self.cursor.fetchone():
                return False

            # Обновляем статус администратора
            self.cursor.execute(
                'UPDATE users SET is_admin = ? WHERE user_id = ?',
                (int(is_admin), user_id)
            )
            self.conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Ошибка при изменении прав администратора: {e}")
            self.conn.rollback()
            return False

    def delete_query(self, query_id: int) -> bool:
        """Удаление запроса по ID"""
        self.cursor.execute('DELETE FROM queries WHERE query_id = ?', (query_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def delete_user_queries(self, user_id: int) -> int:
        """Удаление всех запросов пользователя"""
        self.cursor.execute('DELETE FROM queries WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount

    def close(self):
        """Закрытие соединения с базой данных"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    with Database() as db:
        print(*[user for user in db.get_all_users()], sep='\n')
        print(*[query for query in db.get_all_queries()], sep='\n')
        exit()
        user1 = User(
            user_id=123456789,
            username='legend',
            first_name='sergey',
            last_name='litvinov',
            is_admin=True
        )
        db.add_user(user1)

        user2 = User(
            user_id=987654321,
            username='pidor',
            first_name='vova'
        )
        db.add_user(user2)

        query1 = Query(
            user_id=user1.user_id,
            query_text='random movie'
        )
        db.add_query(query1)

        query2 = Query(
            user_id=user2.user_id,
            query_text='горбатая гора'
        )
        db.add_query(query2)

        print("Админы:")
        for admin in db.get_admins():
            print(f"- {admin.full_name()} (ID: {admin.user_id})")

        print("\nПоследние запросы:")
        for query in db.get_all_queries(limit=3):
            user_info = query.user.full_name() if query.user else f"UserID: {query.user_id}"
            print(f"[{query.query_date}] {user_info}: {query.query_text}")

        first_query = next(db.get_all_queries(limit=1), None)
        if first_query:
            db.delete_query(first_query.query_id)
            print(f"\nУдален запрос ID: {first_query.query_id}")