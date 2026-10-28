import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from uuid import uuid4
import xml.etree.ElementTree as ET

import psycopg2
from psycopg2 import errors, sql
from sqlalchemy.engine import URL

from db.ingestion.ratings import normalize_age_rating, normalize_mpaa_rating


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"


class RatingNormalizationTests(unittest.TestCase):
    def test_supported_age_ratings(self):
        for age in (0, 6, 12, 16, 18):
            for value in (age, str(age), f"{age}+"):
                with self.subTest(value=value):
                    self.assertEqual(normalize_age_rating(value), f"{age}+")
        self.assertIsNone(normalize_age_rating(None))

    def test_supported_mpaa_ratings(self):
        for source, target in (("g", "G"), ("pg", "PG"), ("pg13", "PG-13"),
                               ("r", "R"), ("nc17", "NC-17")):
            for value in (source, source.upper(), target):
                with self.subTest(value=value):
                    self.assertEqual(normalize_mpaa_rating(value), target)
        self.assertIsNone(normalize_mpaa_rating(None))

    def test_unknown_values_are_rejected(self):
        for value in (True, False, "", "unknown", 21, 12.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_age_rating(value)
        for value in ("", "unknown", "NR", 12):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_mpaa_rating(value)


@unittest.skipUnless(os.getenv("KINOPOISK_TEST_PG_DSN"), "KINOPOISK_TEST_PG_DSN is not set")
class MediaIntegrityMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = "kinopoisk_migration_test_" + uuid4().hex
        cls.admin = psycopg2.connect(os.environ["KINOPOISK_TEST_PG_DSN"])
        cls.admin.autocommit = True
        with cls.admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database_name)))
        try:
            parameters = cls.admin.get_dsn_parameters()
            parameters.pop("dbname", None)
            cls.connection = psycopg2.connect(**parameters, dbname=cls.database_name)
            cls.connection.autocommit = True
        except Exception:
            with cls.admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.database_name)))
            cls.admin.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        with cls.admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.database_name)))
        cls.admin.close()

    def setUp(self):
        with self.connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
            cursor.execute((ROOT / "tests/fixtures/legacy_schema.sql").read_text())
            cursor.execute("""
                ALTER TABLE review DROP CONSTRAINT review_media_id_fkey;
                ALTER TABLE user_list_media DROP CONSTRAINT user_list_media_media_id_fkey;
                ALTER TABLE connected_media DROP CONSTRAINT connected_media_media_id_fkey,
                    DROP CONSTRAINT connected_media_parent_id_fkey;
                CREATE TABLE unrelated_table (id integer PRIMARY KEY, value text);
                INSERT INTO unrelated_table VALUES (1, 'unchanged');
                INSERT INTO subscription_type (subscription_type_id, name) VALUES (1, 'basic');
                INSERT INTO user_account (user_id, email, password_hash) VALUES (1, 'test@example.invalid', 'hash');
                INSERT INTO user_list (list_id, user_id, list_name) VALUES (1, 1, 'test');
                INSERT INTO person (person_id) VALUES (1);
                INSERT INTO role (role_id, name) VALUES (1, 'actor');
                INSERT INTO sequels (connection_id, type) VALUES (1, 'sequel');
                INSERT INTO media (media_id, title, age_rating, rating_mpaa) VALUES
                    (1, 'zero', '0', 'g'), (2, 'six', '6', 'pg'),
                    (3, 'twelve', '12', 'pg13'), (4, 'sixteen', '16', 'r'),
                    (5, 'eighteen', '18', 'nc17'), (6, 'unknown', NULL, NULL);
                INSERT INTO media_person_role (id, media_id, person_id, role_id, description)
                    VALUES (1, 1, 1, 1, 'character');
                INSERT INTO season (season_id, media_id, season_number) VALUES (1, 1, 1);
                INSERT INTO episode (episode_id, season_id, episode_number) VALUES (1, 1, 1);
                INSERT INTO review (review_id, user_id, media_id, rating) VALUES (1, 1, 1, 10);
                INSERT INTO user_list_media VALUES (1, 1);
                INSERT INTO connected_media VALUES (1, 2, 1), (2, 1, 1);
                SELECT setval('review_review_id_seq', 1, true),
                    setval('role_role_id_seq', 1, true),
                    setval('subscription_type_subscription_type_id_seq', 1, true),
                    setval('sequels_connection_id_seq', 1, true);
            """)

    def execute(self, statement, parameters=None):
        with self.connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchall() if cursor.description else None

    def migrate(self, filename):
        try:
            if filename.startswith('V'):
                statement = 'BEGIN;\n' + (MIGRATIONS / filename).read_text() + '\nCOMMIT;'
            else:
                statement = (ROOT / 'db/rollbacks' / filename).read_text()
            self.execute(statement)
        except Exception:
            self.execute("ROLLBACK")
            raise

    def pgmigrate(self, *arguments):
        parameters = self.connection.get_dsn_parameters()
        environment = dict(os.environ)
        environment['DATABASE_URL'] = URL.create(
            'postgresql', username=parameters['user'], database=self.database_name,
            query={'host': parameters['host'], 'port': parameters['port']},
        ).render_as_string(hide_password=False)
        return subprocess.run(
            [sys.executable, str(ROOT / 'db/migrate.py'), *arguments],
            env=environment, capture_output=True, text=True, timeout=30,
        )

    def schema(self):
        return (
            self.execute("""SELECT table_name, column_name, data_type, udt_name, is_nullable,
                column_default FROM information_schema.columns WHERE table_schema='public'
                ORDER BY table_name, ordinal_position"""),
            self.execute("""SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)
                FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2"""),
            self.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1"),
        )

    def test_enum_conversion_and_import_compatibility(self):
        self.migrate("V001__media_integrity.sql")
        self.assertEqual(self.execute("SELECT age_rating::text, rating_mpaa::text FROM media ORDER BY media_id"),
                         [("0+", "G"), ("6+", "PG"), ("12+", "PG-13"),
                          ("16+", "R"), ("18+", "NC-17"), (None, None)])
        values = [7, None, "new movie", None, None, None, None, None, None, None,
                  None, None, None, None, normalize_age_rating(12),
                  normalize_mpaa_rating("pg13"), None, None, None, "movie"]
        self.execute((ROOT / "db/sql/media/add_media.sql").read_text(), values)
        self.assertEqual(self.execute("SELECT age_rating::text, rating_mpaa::text FROM media WHERE media_id=7"),
                         [("12+", "PG-13")])
        for column, value in (("age_rating", "21+"), ("rating_mpaa", "NR")):
            with self.subTest(column=column):
                with self.assertRaises(errors.InvalidTextRepresentation):
                    self.execute(sql.SQL("UPDATE media SET {}=%s WHERE media_id=1").format(sql.Identifier(column)), (value,))

    def test_all_four_foreign_keys_and_cascades(self):
        self.migrate("V001__media_integrity.sql")
        self.assertEqual(self.execute("""SELECT conname FROM pg_constraint
            WHERE conname IN ('fk_review_media_id', 'fk_user_list_media_media_id',
                'fk_connected_media_media_id', 'fk_connected_media_parent_id')
            AND condeferrable"""), [])
        invalid = (
            "INSERT INTO review (user_id,media_id) VALUES (1,999)",
            "INSERT INTO user_list_media VALUES (1,999)",
            "INSERT INTO connected_media VALUES (999,2,1)",
            "INSERT INTO connected_media VALUES (2,999,1)",
        )
        for statement in invalid:
            with self.subTest(statement=statement):
                with self.assertRaises(errors.ForeignKeyViolation):
                    self.execute(statement)
        self.execute("DELETE FROM media WHERE media_id=1")
        for table in ("review", "user_list_media", "connected_media"):
            self.assertEqual(self.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))), [(0,)])
        self.assertEqual(self.execute("SELECT count(*) FROM media WHERE media_id=2"), [(1,)])

    def test_unique_names_and_self_reference(self):
        self.migrate("V001__media_integrity.sql")
        for statement in ("INSERT INTO role(name) VALUES ('actor')",
                          "INSERT INTO subscription_type(name) VALUES ('basic')"):
            with self.subTest(statement=statement):
                with self.assertRaises(errors.UniqueViolation):
                    self.execute(statement)
        with self.assertRaises(errors.CheckViolation):
            self.execute("INSERT INTO connected_media VALUES (2,2,1)")

    def test_all_ten_not_null_constraints(self):
        self.migrate("V001__media_integrity.sql")
        fields = (("user_account", "registration_date"), ("review", "user_id"),
                  ("review", "media_id"), ("review", "created_at"), ("user_list", "user_id"),
                  ("media_person_role", "media_id"), ("media_person_role", "person_id"),
                  ("media_person_role", "role_id"), ("season", "media_id"), ("episode", "season_id"))
        for table, column in fields:
            with self.subTest(table=table, column=column):
                with self.assertRaises(errors.NotNullViolation):
                    self.execute(sql.SQL("UPDATE {} SET {}=NULL").format(sql.Identifier(table), sql.Identifier(column)))

    def test_duplicates_survive_v1_and_block_v4(self):
        self.execute("INSERT INTO media_person_role(id,media_id,person_id,role_id,description) VALUES (2,1,1,1,'another character')")
        self.migrate("V001__media_integrity.sql")
        with self.assertRaises(errors.UniqueViolation):
            self.migrate("V004__unique_media_person_role.sql")
        self.assertEqual(self.execute("SELECT description FROM media_person_role ORDER BY id"),
                         [("character",), ("another character",)])
        self.execute("DELETE FROM media_person_role WHERE id=2")
        self.migrate("V004__unique_media_person_role.sql")
        with self.assertRaises(errors.UniqueViolation):
            self.execute("INSERT INTO media_person_role(id,media_id,person_id,role_id) VALUES (3,1,1,1)")
        self.migrate("R004__unique_media_person_role.sql")
        self.execute("INSERT INTO media_person_role(id,media_id,person_id,role_id) VALUES (3,1,1,1)")

    def test_dirty_data_rolls_back_entire_migration(self):
        for statement, exception in (
            ("INSERT INTO review(user_id,media_id) VALUES (1,999)", errors.ForeignKeyViolation),
            ("UPDATE media SET age_rating='21' WHERE media_id=1", errors.InvalidTextRepresentation),
            ("UPDATE review SET user_id=NULL", errors.NotNullViolation),
            ("INSERT INTO role(role_id,name) VALUES (2,'actor')", errors.UniqueViolation),
            ("INSERT INTO connected_media VALUES (2,2,1)", errors.CheckViolation),
        ):
            with self.subTest(statement=statement):
                self.setUp()
                self.execute(statement)
                schema_before = self.schema()
                ratings_before = self.execute("SELECT age_rating,rating_mpaa FROM media ORDER BY media_id")
                with self.assertRaises(exception):
                    self.migrate("V001__media_integrity.sql")
                self.assertEqual(self.schema(), schema_before)
                self.assertEqual(self.execute("SELECT age_rating,rating_mpaa FROM media ORDER BY media_id"), ratings_before)
                self.assertEqual(self.execute("SELECT typname FROM pg_type WHERE typnamespace='public'::regnamespace AND typtype='e'"), [])

    def test_down_restores_original_schema_and_values(self):
        schema_before = self.schema()
        ratings_before = self.execute("SELECT age_rating,rating_mpaa FROM media ORDER BY media_id")
        self.migrate("V001__media_integrity.sql")
        self.migrate("V002__foreign_key_indexes.sql")
        self.migrate("V003__connection_type.sql")
        self.migrate("V004__unique_media_person_role.sql")
        self.migrate("R004__unique_media_person_role.sql")
        self.migrate("R003__connection_type.sql")
        self.migrate("R002__foreign_key_indexes.sql")
        self.migrate("R001__media_integrity.sql")
        self.assertEqual(self.schema(), schema_before)
        self.assertEqual(self.execute("SELECT age_rating,rating_mpaa FROM media ORDER BY media_id"), ratings_before)
        self.assertEqual(self.execute("SELECT * FROM unrelated_table"), [(1, "unchanged")])
        self.migrate("V001__media_integrity.sql")

    def test_foreign_key_indexes_and_rollback(self):
        schema_before = self.schema()
        self.migrate("V002__foreign_key_indexes.sql")
        indexes = dict(self.execute("""SELECT ci.relname, array_agg(a.attname ORDER BY k.position)
            FROM pg_index i JOIN pg_class ci ON ci.oid=i.indexrelid
            CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum, position)
            JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
            WHERE ci.relname IN ('idx_user_account_subscription_type_id',
                'idx_user_list_user_id', 'idx_user_list_media_media_id',
                'idx_media_person_role_role_id', 'idx_connected_media_connection_id')
            GROUP BY ci.relname"""))
        self.assertEqual(indexes, {
            'idx_user_account_subscription_type_id': ['subscription_type_id'],
            'idx_user_list_user_id': ['user_id'],
            'idx_user_list_media_media_id': ['media_id'],
            'idx_media_person_role_role_id': ['role_id'],
            'idx_connected_media_connection_id': ['connection_id'],
        })
        self.migrate("R002__foreign_key_indexes.sql")
        self.assertEqual(self.schema(), schema_before)

    def test_connection_type_rename_and_queries(self):
        from db.ingestion.fill_connections import DatabaseManager

        self.migrate("V003__connection_type.sql")
        self.assertEqual(self.execute("SELECT connection_type_id,name FROM connection_type"), [(1, 'sequel')])
        self.assertEqual(self.execute("SELECT media_id,parent_id,connection_id FROM connected_media ORDER BY media_id"),
                         [(1, 2, 1), (2, 1, 1)])
        self.execute((ROOT / 'db/sql/media/add_connection_type.sql').read_text(), ('spin-off',))
        query = (ROOT / 'db/sql/media/get_or_insert_connection_type.sql').read_text()
        connection_id = self.execute(query, {'name': 'prequel'})[0][0]
        self.assertEqual(self.execute(query, {'name': 'prequel'}), [(connection_id,)])
        self.assertEqual(len(self.execute((ROOT / 'db/sql/media/add_sequels.sql').read_text(), ('adaptation',))), 1)
        self.execute((ROOT / 'db/sql/media/add_connected_media.sql').read_text(), (1, 3, connection_id))
        result = self.execute((ROOT / 'db/sql/media/get_media_by_title.sql').read_text(), ('zero', 'zero'))
        self.assertEqual({item['connection_type'] for item in result[0][20]}, {'sequel', 'prequel'})
        manager = DatabaseManager()
        manager.connection = self.connection
        manager.fetch_existing_connection_types()
        self.assertEqual(manager.get_or_create_connection_type('sequel'), 1)
        crossover = manager.get_or_create_connection_type('crossover')
        self.assertEqual(manager.get_or_create_connection_type('crossover'), crossover)
        manager.insert_connected_media_batch([(3, 4, crossover)])
        self.assertEqual(self.execute("SELECT connection_id FROM connected_media WHERE media_id=3 AND parent_id=4"), [(crossover,)])
        self.execute("DELETE FROM connection_type WHERE connection_type_id=%s", (connection_id,))
        self.assertEqual(self.execute("SELECT count(*) FROM connected_media WHERE connection_id=%s", (connection_id,)), [(0,)])

    def test_connection_type_down_refuses_to_truncate_names(self):
        self.migrate("V003__connection_type.sql")
        self.execute("UPDATE connection_type SET name=%s", ('x' * 60,))
        schema_before = self.schema()
        with self.assertRaises(errors.RaiseException):
            self.migrate("R003__connection_type.sql")
        self.assertEqual(self.schema(), schema_before)
        self.assertEqual(self.execute("SELECT name FROM connection_type"), [('x' * 60,)])

    def test_target_schema_matches_migrations_and_diagrams(self):
        for migration in ('V001__media_integrity', 'V002__foreign_key_indexes',
                          'V003__connection_type', 'V004__unique_media_person_role'):
            self.migrate(migration + '.sql')
        expected = self.schema()
        fields = {}
        for table, column, *_ in expected[0]:
            if table != 'unrelated_table':
                fields.setdefault(table, []).append(column)
        dbml = (ROOT / 'diagrams/kinopoisk-physical.dbml').read_text()
        dbml_fields = {}
        for table, body in re.findall(r'Table (\w+) \{(.*?)\n\}', dbml, re.S):
            dbml_fields[table] = re.findall(r'^  (\w+) [^\n]+\[', body.split('  indexes {')[0].split('  checks {')[0], re.M)
        self.assertEqual(dbml_fields, fields)
        diagram = ET.parse(ROOT / 'diagrams/kinopoisk.drawio')
        for page, prefix in [('logical-crows-foot', 'logical'), ('physical-postgresql', 'physical')]:
            model = diagram.find(f"diagram[@id='{page}']")
            if prefix == 'logical':
                for cell in model.iter('mxCell'):
                    self.assertFalse(cell.get('id', '').endswith('-type'))
                    self.assertNotRegex(cell.get('value', ''), r'\b(SERIAL|varchar|timestamptz|CHECK)\b')
            for table, columns in fields.items():
                names = [cell.get('value') for cell in model.iter('mxCell')
                         if cell.get('parent') == f'{prefix}-{table}' and cell.get('id', '').endswith('-name')]
                self.assertEqual(names, columns, (page, table))
        target_sql = (ROOT / 'diagrams/kinopoisk-physical.sql').read_text()
        self.assertEqual(target_sql, (ROOT / 'db/sql/create_tables.sql').read_text())
        self.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
        self.execute(target_sql)
        self.execute('CREATE TABLE unrelated_table (id integer PRIMARY KEY, value text)')
        self.assertEqual(self.schema(), expected)

    def test_pgmigrate_records_history_and_skips_applied_versions(self):
        before = self.schema()
        plan = self.pgmigrate('-t', '3', 'info')
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(list(json.loads(plan.stdout)), ['1', '2', '3'])
        self.assertEqual(self.schema(), before)
        applied = self.pgmigrate('-t', '3', 'migrate')
        self.assertEqual(applied.returncode, 0, applied.stderr)
        history = self.execute('SELECT version,description,installed_on FROM schema_version ORDER BY version')
        self.assertEqual([row[0] for row in history], [1, 2, 3])
        self.assertEqual(self.execute('SELECT * FROM unrelated_table'), [(1, 'unchanged')])
        repeated = self.pgmigrate('-t', '3', 'migrate')
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(self.execute('SELECT version,description,installed_on FROM schema_version ORDER BY version'), history)
        final = self.pgmigrate('-t', '4', 'migrate')
        self.assertEqual(final.returncode, 0, final.stderr)
        self.assertEqual(self.execute('SELECT version FROM schema_version ORDER BY version'), [(1,), (2,), (3,), (4,)])

    def test_pgmigrate_dry_run_leaves_no_schema_or_history_changes(self):
        before = self.schema()
        ratings = self.execute('SELECT age_rating,rating_mpaa FROM media ORDER BY media_id')
        result = self.pgmigrate('-t', '3', '-n', 'migrate')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.schema(), before)
        self.assertEqual(self.execute('SELECT age_rating,rating_mpaa FROM media ORDER BY media_id'), ratings)
        self.assertEqual(self.execute("SELECT to_regclass('public.schema_version')"), [(None,)])

    def test_pgmigrate_failed_batch_rolls_back_schema_and_history(self):
        self.execute('INSERT INTO media_person_role(id,media_id,person_id,role_id) VALUES (2,1,1,1)')
        before = self.schema()
        result = self.pgmigrate('-t', 'latest', 'migrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('uq_media_person_role', result.stderr)
        self.assertEqual(self.schema(), before)
        self.assertEqual(self.execute("SELECT to_regclass('public.schema_version')"), [(None,)])

    def test_pgmigrate_rollback_checks_and_restores_history(self):
        result = self.pgmigrate('-t', '3', 'migrate')
        self.assertEqual(result.returncode, 0, result.stderr)
        before = self.schema()
        with self.assertRaises(errors.RaiseException):
            self.migrate('R001__media_integrity.sql')
        self.assertEqual(self.schema(), before)
        self.migrate('R003__connection_type.sql')
        self.assertEqual(self.execute('SELECT version FROM schema_version ORDER BY version'), [(1,), (2,)])
        self.assertEqual(self.execute('SELECT connection_id,type FROM sequels'), [(1, 'sequel')])
        reapplied = self.pgmigrate('-t', '3', 'migrate')
        self.assertEqual(reapplied.returncode, 0, reapplied.stderr)
        self.assertEqual(self.schema(), before)
        for filename in ('R003__connection_type.sql', 'R002__foreign_key_indexes.sql', 'R001__media_integrity.sql'):
            self.migrate(filename)
        self.assertEqual(self.execute('SELECT version FROM schema_version'), [])
        self.assertEqual(self.execute('SELECT age_rating,rating_mpaa FROM media WHERE media_id=3'), [('12', 'pg13')])
        self.assertEqual(self.execute('SELECT * FROM unrelated_table'), [(1, 'unchanged')])


if __name__ == "__main__":
    unittest.main()
