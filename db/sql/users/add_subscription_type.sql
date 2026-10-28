INSERT INTO subscription_type (
    name,
    description
) VALUES (%s, %s)
RETURNING subscription_type_id;
