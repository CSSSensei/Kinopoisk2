WITH ins AS (
    INSERT INTO connection_type (name)
    VALUES (%(name)s)
    ON CONFLICT (name) DO NOTHING
    RETURNING connection_type_id
)
SELECT connection_type_id FROM ins
UNION ALL
SELECT connection_type_id FROM connection_type WHERE name = %(name)s
LIMIT 1;
