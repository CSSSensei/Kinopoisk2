BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
        IF NOT EXISTS (
            SELECT FROM public.schema_version
            WHERE version = 6 AND description = 'media relations' AND type = 'auto'
        ) OR EXISTS (SELECT FROM public.schema_version WHERE version > 6) THEN
            RAISE EXCEPTION 'Cannot roll back version 6: migration history does not match';
        END IF;
    END IF;
END;
$$;

DROP TABLE public.media_ingestion_relation;

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        DELETE FROM public.schema_version
        WHERE version = 6 AND description = 'media relations' AND type = 'auto';
    END IF;
END;
$$;
COMMIT;
