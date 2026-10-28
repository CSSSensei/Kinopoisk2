SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

ALTER TABLE public.sequels RENAME TO connection_type;
ALTER TABLE public.connection_type RENAME COLUMN connection_id TO connection_type_id;
ALTER TABLE public.connection_type RENAME COLUMN type TO name;
ALTER TABLE public.connection_type ALTER COLUMN name TYPE varchar(100);
ALTER TABLE public.connection_type RENAME CONSTRAINT sequels_pkey TO connection_type_pkey;
ALTER TABLE public.connection_type RENAME CONSTRAINT sequels_type_key TO connection_type_name_key;
ALTER SEQUENCE public.sequels_connection_id_seq RENAME TO connection_type_connection_type_id_seq;
