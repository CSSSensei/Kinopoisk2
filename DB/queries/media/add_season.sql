INSERT INTO season (
    media_id,
    season_number,
    title
)
VALUES (%s, %s, %s)
RETURNING season_id;
