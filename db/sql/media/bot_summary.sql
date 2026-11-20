m.media_id, m.title, m.release_year, m.rating, m.posterurl, m.posterurlpreview,
m.short_description, m.description,
ARRAY(SELECT g.name FROM kinopoisk.media_genre x JOIN kinopoisk.genre g USING(genre_id)
      WHERE x.media_id=m.media_id ORDER BY g.name) AS genres,
ARRAY(SELECT c.name FROM kinopoisk.media_country x JOIN kinopoisk.country c USING(country_id)
      WHERE x.media_id=m.media_id ORDER BY c.name) AS countries,
ARRAY(SELECT name FROM kinopoisk.bot_credit_names WHERE media_id=m.media_id
      AND role_name IN ('режиссеры','режиссёры','режиссер','режиссёр','director','directors') ORDER BY name) AS directors
