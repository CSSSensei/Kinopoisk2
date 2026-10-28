import os
from pathlib import Path
import sys

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


BASE_DIR = Path(__file__).resolve().parent
PG_ENVIRONMENT = {
    'host': 'PGHOST',
    'port': 'PGPORT',
    'dbname': 'PGDATABASE',
    'user': 'PGUSER',
    'password': 'PGPASSWORD',
    'sslmode': 'PGSSLMODE',
    'sslrootcert': 'PGSSLROOTCERT',
    'sslcert': 'PGSSLCERT',
    'sslkey': 'PGSSLKEY',
    'connect_timeout': 'PGCONNECT_TIMEOUT',
    'options': 'PGOPTIONS',
}


def configure_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        database_url = dotenv_values(BASE_DIR.parent / '.env').get('DATABASE_URL')
    if not database_url:
        raise ValueError('DATABASE_URL is required')
    url = make_url(database_url)
    if url.get_backend_name() not in {'postgres', 'postgresql'}:
        raise ValueError('DATABASE_URL must use PostgreSQL')
    parameters = url.translate_connect_args(username='user', database='dbname')
    parameters.update(url.query)
    for key in parameters:
        if key not in PG_ENVIRONMENT:
            raise ValueError(f'Unsupported PostgreSQL connection option: {key}')
    for key in ('host', 'port', 'dbname', 'user', 'password'):
        os.environ.pop(PG_ENVIRONMENT[key], None)
    for key, value in parameters.items():
        if not isinstance(value, (str, int)):
            raise ValueError(f'PostgreSQL connection option must have one value: {key}')
        os.environ[PG_ENVIRONMENT[key]] = str(value)
    os.environ.setdefault('PGCONNECT_TIMEOUT', '10')
    os.environ.pop('DATABASE_URL', None)


def main():
    if not {'-h', '--help'} & set(sys.argv[1:]):
        configure_connection()
    os.execv(sys.executable, [sys.executable, '-m', 'pgmigrate', '-d', str(BASE_DIR),
                             '-c', '', '--check_serial_versions', *sys.argv[1:]])


if __name__ == '__main__':
    main()
