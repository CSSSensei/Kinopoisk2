INSERT INTO episode (
    season_id,
    episode_number,
    title,
    duration,
    description
)
VALUES (%s, %s, %s, %s, %s)
RETURNING episode_id;
