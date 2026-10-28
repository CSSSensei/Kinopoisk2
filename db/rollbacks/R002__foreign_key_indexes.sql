BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
        IF NOT EXISTS (
            SELECT FROM public.schema_version
            WHERE version = 2 AND description = 'foreign key indexes' AND type = 'auto'
        ) OR EXISTS (SELECT FROM public.schema_version WHERE version > 2) THEN
            RAISE EXCEPTION 'Cannot roll back version 2: migration history does not match';
        END IF;
    END IF;
END;
$$;


DROP INDEX public.idx_user_account_subscription_type_id;
DROP INDEX public.idx_user_list_user_id;
DROP INDEX public.idx_user_list_media_media_id;
DROP INDEX public.idx_media_person_role_role_id;
DROP INDEX public.idx_connected_media_connection_id;

DO $$
BEGIN
    IF to_regclass('public.schema_version') IS NOT NULL THEN
        DELETE FROM public.schema_version
        WHERE version = 2 AND description = 'foreign key indexes' AND type = 'auto';
    END IF;
END;
$$;

COMMIT;
