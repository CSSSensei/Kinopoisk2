m.votes, m.duration, m.type, m.age_rating::text, m.rating_mpaa::text,
m.budget_value, m.fees_world, m.trailer, m.top250,
ARRAY(SELECT name FROM kinopoisk.bot_credit_names WHERE media_id=m.media_id
      AND role_name IN ('актеры','актёры','актер','актёр','actor','actors') ORDER BY name) AS actors,
coalesce((SELECT json_agg(json_build_object('id', target.media_id, 'title', target.title, 'kind', t.name)
                          ORDER BY t.name, target.title, target.media_id)
          FROM kinopoisk.connected_media c JOIN kinopoisk.connection_type t ON t.connection_type_id=c.connection_id
          JOIN kinopoisk.media target ON target.media_id=c.parent_id WHERE c.media_id=m.media_id),'[]') AS relations,
coalesce((SELECT json_agg(json_build_object('id',target.media_id,'title',target.title)
                          ORDER BY r.position,target.media_id)
          FROM kinopoisk.media_recommendation r JOIN kinopoisk.media target ON target.media_id=r.recommended_id
          WHERE r.media_id=m.media_id),'[]') AS similar,
coalesce((SELECT json_agg(json_build_object('body',f.body,'is_spoiler',f.is_spoiler) ORDER BY f.position)
          FROM kinopoisk.media_fact f WHERE f.media_id=m.media_id),'[]') AS facts
