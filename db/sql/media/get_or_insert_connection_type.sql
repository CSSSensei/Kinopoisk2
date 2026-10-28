WITH ins AS (
    INSERT INTO sequels (type)
    VALUES (%(type)s)
    ON CONFLICT (type) DO NOTHING
    RETURNING connection_id
)
SELECT connection_id FROM ins
UNION ALL
SELECT connection_id FROM sequels WHERE type = %(type)s
LIMIT 1;
