BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
DO $$
BEGIN
    IF (SELECT max(version) FROM public.schema_version) IS DISTINCT FROM 8 OR
       NOT EXISTS (SELECT FROM public.schema_version WHERE version=8 AND description='project namespaces') THEN
        RAISE EXCEPTION 'Expected project namespaces as the latest migration';
    END IF;
END $$;
ALTER TABLE telegram.queries RENAME TO telegram_queries;
ALTER TABLE telegram.users RENAME TO telegram_users;
ALTER TABLE telegram.telegram_queries SET SCHEMA public;
ALTER TABLE telegram.telegram_users SET SCHEMA public;
ALTER TYPE kinopoisk.age_rating_enum SET SCHEMA public;
ALTER TYPE kinopoisk.mpaa_rating_enum SET SCHEMA public;
ALTER TYPE kinopoisk.media_ingestion_state SET SCHEMA public;
ALTER TABLE kinopoisk.media SET SCHEMA public;
ALTER TABLE kinopoisk.genre SET SCHEMA public;
ALTER TABLE kinopoisk.country SET SCHEMA public;
ALTER TABLE kinopoisk.media_genre SET SCHEMA public;
ALTER TABLE kinopoisk.media_country SET SCHEMA public;
ALTER TABLE kinopoisk.person SET SCHEMA public;
ALTER TABLE kinopoisk.role SET SCHEMA public;
ALTER TABLE kinopoisk.media_person_role SET SCHEMA public;
ALTER TABLE kinopoisk.connection_type SET SCHEMA public;
ALTER TABLE kinopoisk.connected_media SET SCHEMA public;
ALTER TABLE kinopoisk.season SET SCHEMA public;
ALTER TABLE kinopoisk.episode SET SCHEMA public;
ALTER TABLE kinopoisk.subscription_type SET SCHEMA public;
ALTER TABLE kinopoisk.user_account SET SCHEMA public;
ALTER TABLE kinopoisk.review SET SCHEMA public;
ALTER TABLE kinopoisk.user_list SET SCHEMA public;
ALTER TABLE kinopoisk.user_list_media SET SCHEMA public;
ALTER TABLE kinopoisk.media_ingestion_job SET SCHEMA public;
ALTER TABLE kinopoisk.media_ingestion_relation SET SCHEMA public;
ALTER TABLE kinopoisk.media_alias SET SCHEMA public;
ALTER TABLE kinopoisk.media_fact SET SCHEMA public;
ALTER TABLE kinopoisk.media_recommendation SET SCHEMA public;
ALTER VIEW kinopoisk.bot_credit_names SET SCHEMA public;
DROP SCHEMA telegram, kinopoisk RESTRICT;
DELETE FROM public.schema_version WHERE version=8;
COMMIT;
