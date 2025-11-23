INSERT INTO genre (name)
VALUES (%s)
RETURNING genre_id;
