INSERT INTO media (
    media_id
    title,
    ru_title,
    en_title,
    original_title,
    description,
    short_description,
    slogan,
    release_year,
    duration,
    posterUrl,
    posterUrlPreview,
    coverUrl,
    logoUrl,
    age_rating,
    rating_mpaa,
    budget_value,
    fees_world,
    type
)
VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s
)
RETURNING media_id;
