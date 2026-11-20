import os
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import URL


@contextmanager
def catalog_database():
    db_dir = Path(__file__).resolve().parents[1] / "db"
    name = "kinopoisk_catalog_test_" + uuid4().hex
    dsn = os.environ["KINOPOISK_TEST_PG_DSN"]
    with closing(psycopg2.connect(dsn)) as admin:
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            params = admin.get_dsn_parameters()
            with closing(psycopg2.connect(dsn, dbname=name)) as conn, conn, conn.cursor() as cur:
                cur.execute((db_dir / "sql/create_tables.sql").read_text())
                for migration in sorted((db_dir / "migrations").glob("V*.sql")):
                    if int(migration.name[1:4]) > 4:
                        cur.execute(migration.read_text())
            yield URL.create(
                "postgresql", username=params["user"], password=admin.info.password, database=name,
                query={"host": params["host"], "port": params["port"]},
            ).render_as_string(hide_password=False)
        finally:
            with admin.cursor() as cur:
                cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
