SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';
SET LOCAL search_path = public, pg_catalog;

LOCK TABLE public.connected_media, public.episode, public.media,
    public.media_person_role, public.review, public.role, public.season,
    public.subscription_type, public.user_account, public.user_list,
    public.user_list_media IN ACCESS EXCLUSIVE MODE;

CREATE TYPE public.age_rating_enum AS ENUM ('0+', '6+', '12+', '16+', '18+');
CREATE TYPE public.mpaa_rating_enum AS ENUM ('G', 'PG', 'PG-13', 'R', 'NC-17');

ALTER TABLE public.media
    ALTER COLUMN age_rating TYPE public.age_rating_enum
    USING (
        CASE
            WHEN age_rating IN ('0', '6', '12', '16', '18') THEN age_rating || '+'
            ELSE age_rating
        END
    )::public.age_rating_enum,
    ALTER COLUMN rating_mpaa TYPE public.mpaa_rating_enum
    USING (
        CASE rating_mpaa
            WHEN 'g' THEN 'G'
            WHEN 'pg' THEN 'PG'
            WHEN 'pg13' THEN 'PG-13'
            WHEN 'r' THEN 'R'
            WHEN 'nc17' THEN 'NC-17'
            ELSE rating_mpaa
        END
    )::public.mpaa_rating_enum;

ALTER TABLE public.review
    ADD CONSTRAINT fk_review_media_id FOREIGN KEY (media_id)
        REFERENCES public.media (media_id) ON DELETE CASCADE,
    ALTER COLUMN user_id SET NOT NULL,
    ALTER COLUMN media_id SET NOT NULL,
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE public.user_list_media
    ADD CONSTRAINT fk_user_list_media_media_id FOREIGN KEY (media_id)
        REFERENCES public.media (media_id) ON DELETE CASCADE;

ALTER TABLE public.connected_media
    ADD CONSTRAINT fk_connected_media_media_id FOREIGN KEY (media_id)
        REFERENCES public.media (media_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_connected_media_parent_id FOREIGN KEY (parent_id)
        REFERENCES public.media (media_id) ON DELETE CASCADE,
    ADD CONSTRAINT chk_connected_media_not_self CHECK (media_id <> parent_id);

ALTER TABLE public.subscription_type
    ADD CONSTRAINT uq_subscription_type_name UNIQUE (name);

ALTER TABLE public.role
    ADD CONSTRAINT uq_role_name UNIQUE (name);

ALTER TABLE public.user_account
    ALTER COLUMN registration_date SET NOT NULL;

ALTER TABLE public.user_list
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE public.media_person_role
    ALTER COLUMN media_id SET NOT NULL,
    ALTER COLUMN person_id SET NOT NULL,
    ALTER COLUMN role_id SET NOT NULL;

ALTER TABLE public.season
    ALTER COLUMN media_id SET NOT NULL;

ALTER TABLE public.episode
    ALTER COLUMN season_id SET NOT NULL;
