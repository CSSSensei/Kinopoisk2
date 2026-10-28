INSERT INTO country (name)
VALUES (%s)
RETURNING country_id;
