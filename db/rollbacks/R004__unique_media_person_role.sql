BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
        IF NOT EXISTS (
            SELECT FROM public.schema_version
            WHERE version = 4 AND description = 'unique media person role' AND type = 'auto'
        ) OR EXISTS (SELECT FROM public.schema_version WHERE version > 4) THEN
            RAISE EXCEPTION 'Cannot roll back version 4: migration history does not match';
        END IF;
    END IF;
END;
$$;


ALTER TABLE public.media_person_role
    DROP CONSTRAINT uq_media_person_role;

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        DELETE FROM public.schema_version
        WHERE version = 4 AND description = 'unique media person role' AND type = 'auto';
    END IF;
END;
$$;

COMMIT;
