INSERT INTO connected_media (
    media_id,
    parent_id,
    connection_id
)
VALUES (%s, %s, %s)
ON CONFLICT (media_id, parent_id, connection_id) 
DO UPDATE SET connection_id = EXCLUDED.connection_id;
