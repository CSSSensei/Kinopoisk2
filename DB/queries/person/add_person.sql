INSERT INTO person (
    person_id,
    ru_name,
    en_name,
    photo_url,
    birth_date,
VALUES (%s, %s, %s)
RETURNING person_id;
