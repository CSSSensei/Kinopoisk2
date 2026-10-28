SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

CREATE TYPE public.media_ingestion_state AS ENUM ('pending', 'running', 'failed');

CREATE TABLE public.media_ingestion_job (
    media_id integer PRIMARY KEY CHECK (media_id > 0),
    source text NOT NULL,
    priority integer NOT NULL DEFAULT 0,
    state public.media_ingestion_state NOT NULL DEFAULT 'pending',
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    lease_token uuid,
    lease_until timestamptz,
    last_success_at timestamptz,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((state = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL)),
    CHECK ((lease_token IS NULL) = (lease_until IS NULL))
);

CREATE INDEX media_ingestion_pending_idx
    ON public.media_ingestion_job (priority DESC, next_attempt_at, media_id)
    WHERE state = 'pending';
CREATE INDEX media_ingestion_lease_idx ON public.media_ingestion_job (lease_until)
    WHERE state = 'running';
CREATE INDEX media_ingestion_owner_idx ON public.media_ingestion_job (lease_token)
    WHERE state = 'running';

