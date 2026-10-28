BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
        IF NOT EXISTS (
            SELECT FROM public.schema_version
            WHERE version = 1 AND description = 'media integrity' AND type = 'auto'
        ) OR EXISTS (SELECT FROM public.schema_version WHERE version > 1) THEN
            RAISE EXCEPTION 'Cannot roll back version 1: migration history does not match';
        END IF;
    END IF;
END;
$$;

SET LOCAL search_path = public, pg_catalog;

LOCK TABLE public.connected_media, public.episode, public.media,
    public.media_person_role, public.review, public.role, public.season,
    public.subscription_type, public.user_account, public.user_list,
    public.user_list_media IN ACCESS EXCLUSIVE MODE;

ALTER TABLE public.media
    ALTER COLUMN age_rating TYPE varchar(20)
        USING replace(age_rating::text, '+', ''),
    ALTER COLUMN rating_mpaa TYPE varchar(10)
        USING lower(replace(rating_mpaa::text, '-', ''));

DROP TYPE public.age_rating_enum;
DROP TYPE public.mpaa_rating_enum;

ALTER TABLE public.review
    DROP CONSTRAINT fk_review_media_id,
    ALTER COLUMN user_id DROP NOT NULL,
    ALTER COLUMN media_id DROP NOT NULL,
    ALTER COLUMN created_at DROP NOT NULL;

ALTER TABLE public.user_list_media
    DROP CONSTRAINT fk_user_list_media_media_id;

ALTER TABLE public.connected_media
    DROP CONSTRAINT fk_connected_media_media_id,
    DROP CONSTRAINT fk_connected_media_parent_id,
    DROP CONSTRAINT chk_connected_media_not_self;

ALTER TABLE public.subscription_type
    DROP CONSTRAINT uq_subscription_type_name;

ALTER TABLE public.role
    DROP CONSTRAINT uq_role_name;

ALTER TABLE public.user_account
    ALTER COLUMN registration_date DROP NOT NULL;

ALTER TABLE public.user_list
    ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE public.media_person_role
    ALTER COLUMN media_id DROP NOT NULL,
    ALTER COLUMN person_id DROP NOT NULL,
    ALTER COLUMN role_id DROP NOT NULL;

ALTER TABLE public.season
    ALTER COLUMN media_id DROP NOT NULL;

ALTER TABLE public.episode
    ALTER COLUMN season_id DROP NOT NULL;

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        DELETE FROM public.schema_version
        WHERE version = 1 AND description = 'media integrity' AND type = 'auto';
    END IF;
END;
$$;

COMMIT;
