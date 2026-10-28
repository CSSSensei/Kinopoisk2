SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

CREATE INDEX idx_user_account_subscription_type_id
    ON public.user_account (subscription_type_id);

CREATE INDEX idx_user_list_user_id
    ON public.user_list (user_id);

CREATE INDEX idx_user_list_media_media_id
    ON public.user_list_media (media_id);

CREATE INDEX idx_media_person_role_role_id
    ON public.media_person_role (role_id);

CREATE INDEX idx_connected_media_connection_id
    ON public.connected_media (connection_id);
