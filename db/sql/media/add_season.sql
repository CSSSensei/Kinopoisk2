INSERT INTO season (
    media_id,
    season_number,
    release_year
)
VALUES (%s, %s, %s)
ON CONFLICT (media_id, season_number)
DO UPDATE SET release_year = EXCLUDED.release_year
RETURNING season_id;
