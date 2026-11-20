BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = public, pg_catalog;
LOCK TABLE schema_version IN EXCLUSIVE MODE;
DO $$
BEGIN
    IF (SELECT max(version) FROM schema_version) IS DISTINCT FROM 7 OR
        NOT EXISTS (SELECT FROM schema_version WHERE version=7 AND description='telegram catalog') THEN
        RAISE EXCEPTION 'Expected telegram catalog as the latest migration';
    END IF;
END $$;
-- telegram_users and telegram_queries can predate this migration.
DROP VIEW bot_credit_names;
DROP TABLE media_alias, media_fact, media_recommendation;
ALTER TABLE media DROP COLUMN top250, DROP COLUMN top10, DROP COLUMN rating_imdb, DROP COLUMN votes_imdb, DROP COLUMN content_id;
DELETE FROM schema_version WHERE version=7;
COMMIT;
