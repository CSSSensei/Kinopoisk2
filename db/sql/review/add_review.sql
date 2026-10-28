INSERT INTO review (
    user_id,
    media_id,
    rating,
    comment_text,
    created_at
)
VALUES (%s, %s, %s, %s, %s)
RETURNING review_id;
