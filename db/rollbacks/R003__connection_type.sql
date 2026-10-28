BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
        IF NOT EXISTS (
            SELECT FROM public.schema_version
            WHERE version = 3 AND description = 'connection type' AND type = 'auto'
        ) OR EXISTS (SELECT FROM public.schema_version WHERE version > 3) THEN
            RAISE EXCEPTION 'Cannot roll back version 3: migration history does not match';
        END IF;
    END IF;
END;
$$;


LOCK TABLE public.connection_type IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (SELECT FROM public.connection_type WHERE length(name) > 50) THEN
        RAISE EXCEPTION 'Cannot roll back: connection_type.name contains values longer than 50 characters';
    END IF;
END;
$$;

ALTER TABLE public.connection_type ALTER COLUMN name TYPE varchar(50);
ALTER TABLE public.connection_type RENAME CONSTRAINT connection_type_pkey TO sequels_pkey;
ALTER TABLE public.connection_type RENAME CONSTRAINT connection_type_name_key TO sequels_type_key;
ALTER SEQUENCE public.connection_type_connection_type_id_seq RENAME TO sequels_connection_id_seq;
ALTER TABLE public.connection_type RENAME COLUMN connection_type_id TO connection_id;
ALTER TABLE public.connection_type RENAME COLUMN name TO type;
ALTER TABLE public.connection_type RENAME TO sequels;

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        DELETE FROM public.schema_version
        WHERE version = 3 AND description = 'connection type' AND type = 'auto';
    END IF;
END;
$$;

COMMIT;
