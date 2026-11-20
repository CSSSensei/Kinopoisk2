SET LOCAL lock_timeout = '5s';
CREATE SCHEMA kinopoisk;
CREATE SCHEMA telegram;

ALTER TYPE public.age_rating_enum SET SCHEMA kinopoisk;
ALTER TYPE public.mpaa_rating_enum SET SCHEMA kinopoisk;
ALTER TYPE public.media_ingestion_state SET SCHEMA kinopoisk;
ALTER TABLE public.media SET SCHEMA kinopoisk;
ALTER TABLE public.genre SET SCHEMA kinopoisk;
ALTER TABLE public.country SET SCHEMA kinopoisk;
ALTER TABLE public.media_genre SET SCHEMA kinopoisk;
ALTER TABLE public.media_country SET SCHEMA kinopoisk;
ALTER TABLE public.person SET SCHEMA kinopoisk;
ALTER TABLE public.role SET SCHEMA kinopoisk;
ALTER TABLE public.media_person_role SET SCHEMA kinopoisk;
ALTER TABLE public.connection_type SET SCHEMA kinopoisk;
ALTER TABLE public.connected_media SET SCHEMA kinopoisk;
ALTER TABLE public.season SET SCHEMA kinopoisk;
ALTER TABLE public.episode SET SCHEMA kinopoisk;
ALTER TABLE public.subscription_type SET SCHEMA kinopoisk;
ALTER TABLE public.user_account SET SCHEMA kinopoisk;
ALTER TABLE public.review SET SCHEMA kinopoisk;
ALTER TABLE public.user_list SET SCHEMA kinopoisk;
ALTER TABLE public.user_list_media SET SCHEMA kinopoisk;
ALTER TABLE public.media_ingestion_job SET SCHEMA kinopoisk;
ALTER TABLE public.media_ingestion_relation SET SCHEMA kinopoisk;
ALTER TABLE public.media_alias SET SCHEMA kinopoisk;
ALTER TABLE public.media_fact SET SCHEMA kinopoisk;
ALTER TABLE public.media_recommendation SET SCHEMA kinopoisk;
ALTER VIEW public.bot_credit_names SET SCHEMA kinopoisk;

ALTER TABLE public.telegram_users SET SCHEMA telegram;
ALTER TABLE public.telegram_queries SET SCHEMA telegram;
ALTER TABLE telegram.telegram_users RENAME TO users;
ALTER TABLE telegram.telegram_queries RENAME TO queries;

-- Existing relation and column grants still require USAGE on the new namespace.
DO $$
DECLARE
    item record;
BEGIN
    FOR item IN
        WITH moved AS (
            SELECT n.nspname,c.oid,c.relowner,c.relacl FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('kinopoisk','telegram') AND c.relkind IN ('r','S','v')
        ), recipients AS (
            SELECT nspname,relowner AS grantee FROM moved
            UNION SELECT nspname,acl.grantee FROM moved CROSS JOIN LATERAL aclexplode(relacl) acl
            UNION SELECT nspname,acl.grantee FROM moved m JOIN pg_attribute a ON a.attrelid=m.oid
                  CROSS JOIN LATERAL aclexplode(a.attacl) acl
        )
        SELECT nspname, CASE WHEN grantee=0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(grantee)) END AS role_sql
        FROM recipients
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO %s', item.nspname,item.role_sql);
    END LOOP;
END $$;
