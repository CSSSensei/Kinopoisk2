INSERT INTO media_person_role (
    media_id,
    person_id,
    role_id,
    description
)
VALUES (%s, %s, %s, %s)
RETURNING id;
