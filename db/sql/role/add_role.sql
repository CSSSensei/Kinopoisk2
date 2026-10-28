INSERT INTO role (name)
VALUES (%s)
RETURNING role_id;
