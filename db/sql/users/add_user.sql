INSERT INTO user_account (
    email,
    password_hash,
    full_name,
    registration_date,
    subscription_type_id,
    subscription_expiry_date
)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING user_id;
