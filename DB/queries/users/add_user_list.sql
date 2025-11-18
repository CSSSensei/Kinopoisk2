INSERT INTO user_list (
    user_id,
    list_name
)
VALUES (%s, %s)
RETURNING list_id;
