INSERT INTO episode (
    season_id,
    episode_number,
    title,
    release_date,
    description
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (season_id, episode_number)
DO UPDATE SET
    title = EXCLUDED.title,
    release_date = EXCLUDED.release_date,
    description = EXCLUDED.description
RETURNING episode_id;
