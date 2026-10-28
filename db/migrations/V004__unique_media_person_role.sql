SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

ALTER TABLE public.media_person_role
    ADD CONSTRAINT uq_media_person_role UNIQUE (media_id, person_id, role_id);
