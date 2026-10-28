INSERT INTO connection_type (name)
VALUES (%s)
RETURNING connection_type_id;
