SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

CREATE TABLE public.media_ingestion_relation (
    media_id integer NOT NULL REFERENCES public.media(media_id) ON DELETE CASCADE,
    related_media_id integer NOT NULL CHECK (related_media_id > 0),
    connection_id integer NOT NULL REFERENCES public.connection_type(connection_type_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (media_id, related_media_id, connection_id),
    CHECK (media_id <> related_media_id)
);

CREATE INDEX media_ingestion_relation_target_idx
    ON public.media_ingestion_relation (related_media_id);
