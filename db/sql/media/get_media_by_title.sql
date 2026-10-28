-- Получение всей информации о фильме по названию, включая сиквелы, жанры, страны и актеров
-- Улучшенный поиск: регистронезависимый, не строгий к ошибкам, но релевантный
WITH media_info AS (
    SELECT
        m.media_id,
        m.imdb_id,
        m.title,
        m.rating,
        m.votes,
        m.en_title,
        m.description,
        m.short_description,
        m.slogan,
        m.release_year,
        m.duration,
        m.posterUrl,
        m.posterUrlPreview,
        m.logoUrl,
        m.age_rating,
        m.rating_mpaa,
        m.budget_value,
        m.fees_world,
        m.trailer,
        m.type
    FROM media m
    WHERE LOWER(m.title) LIKE LOWER('%' || %s || '%') OR LOWER(m.en_title) LIKE LOWER('%' || %s || '%')
    ORDER BY m.votes DESC NULLS LAST, m.rating DESC NULLS LAST
    LIMIT 1
),
sequels_info AS (
    SELECT
        cm.media_id,
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'parent_id', cm.parent_id,
                'connection_type', s.type,
                'parent_title', parent.title
            )
        ) AS sequels
    FROM connected_media cm
    JOIN sequels s ON cm.connection_id = s.connection_id
    JOIN media parent ON cm.parent_id = parent.media_id
    WHERE cm.media_id = (SELECT media_id FROM media_info)
    GROUP BY cm.media_id
),
genres_info AS (
    SELECT
        mg.media_id,
        JSON_AGG(g.name) AS genres
    FROM media_genre mg
    JOIN genre g ON mg.genre_id = g.genre_id
    WHERE mg.media_id = (SELECT media_id FROM media_info)
    GROUP BY mg.media_id
),
countries_info AS (
    SELECT
        mc.media_id,
        JSON_AGG(c.name) AS countries
    FROM media_country mc
    JOIN country c ON mc.country_id = c.country_id
    WHERE mc.media_id = (SELECT media_id FROM media_info)
    GROUP BY mc.media_id
),
actors_info AS (
    SELECT
        mpr.media_id,
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'person_id', p.person_id,
                'ru_name', p.ru_name,
                'en_name', p.en_name,
                'role', r.name,
                'description', mpr.description
            )
        ) AS actors
    FROM media_person_role mpr
    JOIN person p ON mpr.person_id = p.person_id
    JOIN role r ON mpr.role_id = r.role_id
    WHERE mpr.media_id = (SELECT media_id FROM media_info)
    GROUP BY mpr.media_id
)
SELECT
    mi.*,
    si.sequels,
    gi.genres,
    ci.countries,
    ai.actors
FROM media_info mi
LEFT JOIN sequels_info si ON mi.media_id = si.media_id
LEFT JOIN genres_info gi ON mi.media_id = gi.media_id
LEFT JOIN countries_info ci ON mi.media_id = ci.media_id
LEFT JOIN actors_info ai ON mi.media_id = ai.media_id;
