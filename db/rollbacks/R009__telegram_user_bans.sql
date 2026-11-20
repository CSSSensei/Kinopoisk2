BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.schema_version IN EXCLUSIVE MODE;
DO $$
BEGIN
    IF (SELECT max(version) FROM public.schema_version) IS DISTINCT FROM 9 OR
       NOT EXISTS (SELECT FROM public.schema_version WHERE version=9 AND description='telegram user bans') THEN
        RAISE EXCEPTION 'Expected telegram user bans as the latest migration';
    END IF;
END $$;
ALTER TABLE telegram.users DROP COLUMN is_banned;
DELETE FROM public.schema_version WHERE version=9;
COMMIT;
