INSERT INTO media (
    media_id,
    imdb_id,
    title,
    rating,
    votes,
    en_title,
    description,
    short_description,
    slogan,
    release_year,
    duration,
    posterUrl,
    posterUrlPreview,
    logoUrl,
    age_rating,
    rating_mpaa,
    budget_value,
    fees_world,
    trailer,
    type
)
VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s
)
RETURNING media_id;
