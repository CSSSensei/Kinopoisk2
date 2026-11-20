SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = public, pg_catalog;

CREATE TABLE IF NOT EXISTS telegram_users (
    user_id bigint PRIMARY KEY, username text, first_name text, last_name text,
    is_admin boolean NOT NULL DEFAULT false,
    registration_date timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS telegram_queries (
    query_id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES telegram_users ON DELETE CASCADE,
    query_text text NOT NULL, query_date timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_telegram_queries_user_date ON telegram_queries (user_id, query_date);

ALTER TABLE media
    ADD COLUMN top250 integer,
    ADD COLUMN top10 integer,
    ADD COLUMN rating_imdb double precision,
    ADD COLUMN votes_imdb integer,
    ADD COLUMN content_id text;
CREATE TABLE media_alias (
    media_id integer REFERENCES media ON DELETE CASCADE, name text NOT NULL,
    PRIMARY KEY (media_id, name)
);
CREATE TABLE media_fact (
    media_id integer REFERENCES media ON DELETE CASCADE, position integer NOT NULL,
    body text NOT NULL, is_spoiler boolean NOT NULL DEFAULT false, PRIMARY KEY (media_id, position)
);
CREATE TABLE media_recommendation (
    media_id integer REFERENCES media ON DELETE CASCADE,
    recommended_id integer NOT NULL,
    position integer NOT NULL,
    PRIMARY KEY (media_id, recommended_id), CHECK (media_id <> recommended_id AND recommended_id > 0)
);
CREATE VIEW bot_credit_names AS
SELECT DISTINCT x.media_id, lower(r.name) AS role_name, coalesce(nullif(p.ru_name,''),nullif(p.en_name,'')) AS name
FROM media_person_role x JOIN person p USING(person_id) JOIN role r USING(role_id)
WHERE coalesce(nullif(p.ru_name,''),nullif(p.en_name,'')) IS NOT NULL;
