from collections import defaultdict

from psycopg2 import sql
from psycopg2.extras import Json, execute_values


_JSON_COLUMNS = {'budget_value', 'fees_world'}


def _payload(rows):
    return [{column: value.adapted if isinstance(value, Json) else value
             for column, value in row.items()} for row in rows]


def upsert_rows(cursor, table: str, rows: list[dict], key: str | tuple[str, ...]) -> dict:
    keys = (key,) if isinstance(key, str) else key

    def identity(values):
        return values[0] if isinstance(key, str) else tuple(values)

    changes = {}
    groups = defaultdict(dict)
    for row in rows:
        groups[tuple(sorted(row))][identity([row[column] for column in keys])] = row
    identifiers = sql.SQL(', ').join(map(sql.Identifier, keys))
    joins = sql.SQL(' AND ').join(
        sql.SQL('target.{} = source.{}').format(sql.Identifier(column), sql.Identifier(column))
        for column in keys
    )
    returning = sql.SQL(', ').join(sql.Identifier('target', column) for column in keys)
    for columns, records in groups.items():
        statement = sql.SQL('INSERT INTO {} ({}) VALUES %s ON CONFLICT ({}) DO NOTHING RETURNING {}').format(
            sql.Identifier(table), sql.SQL(', ').join(map(sql.Identifier, columns)), identifiers, identifiers,
        )
        inserted = execute_values(cursor, statement.as_string(cursor),
                                  [tuple(row[column] for column in columns) for row in records.values()],
                                  page_size=1000, fetch=True)
        inserted_ids = {identity(row) for row in inserted}
        changes.update({item: 'INSERT' for item in inserted_ids})
        records = {item: row for item, row in records.items() if item not in inserted_ids}
        if not records:
            continue
        changed = [column for column in columns if column not in keys]
        updated_ids = set()
        if changed:
            updates = sql.SQL(', ').join(
                sql.SQL('{} = source.{}').format(sql.Identifier(column), sql.Identifier(column))
                for column in changed
            )
            comparisons = []
            for column in changed:
                cast = sql.SQL('::jsonb') if column in _JSON_COLUMNS else sql.SQL('')
                comparisons.append(sql.SQL('target.{}{} IS DISTINCT FROM source.{}{}').format(
                    sql.Identifier(column), cast, sql.Identifier(column), cast,
                ))
            statement = sql.SQL('''UPDATE {} AS target SET {}
                FROM json_populate_recordset(NULL::{}, %s) AS source
                WHERE {} AND ({}) RETURNING {}''').format(
                    sql.Identifier(table), updates, sql.Identifier(table), joins,
                    sql.SQL(' OR ').join(comparisons), returning,
                )
            cursor.execute(statement, (Json(_payload(records.values())),))
            updated_ids = {identity(row) for row in cursor.fetchall()}
            changes.update({item: 'UPDATE' for item in updated_ids})
        unchanged_ids = set(records) - updated_ids
        if unchanged_ids:
            statement = sql.SQL('''SELECT {} FROM {} AS target
                JOIN json_populate_recordset(NULL::{}, %s) AS source ON {}
                FOR KEY SHARE OF target''').format(returning, sql.Identifier(table), sql.Identifier(table), joins)
            cursor.execute(statement, (Json(_payload(records[item] for item in unchanged_ids)),))
            if {identity(row) for row in cursor.fetchall()} != unchanged_ids:
                raise RuntimeError(f'{table}: rows disappeared during batch save; retry required')
    return changes
