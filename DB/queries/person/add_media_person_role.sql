INSERT INTO media_person_role (
    media_id,
    person_id,
    role_id
)
VALUES (%s, %s, %s)
RETURNING id;
