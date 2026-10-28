CREATE TABLE IF NOT EXISTS subscription_type (
    subscription_type_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS user_account (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    registration_date DATE DEFAULT CURRENT_DATE,
    subscription_type_id INT REFERENCES subscription_type(subscription_type_id),
    subscription_expiry_date DATE
);

CREATE TABLE IF NOT EXISTS media  (
    media_id SERIAL PRIMARY KEY,
    imdb_id VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    rating FLOAT,
    votes INT,
    en_title VARCHAR(255),
    description TEXT,
    short_description TEXT,
    slogan TEXT,
    release_year INT,
    duration INT,
    posterUrl TEXT,
    posterUrlPreview TEXT,
    logoUrl TEXT,
    age_rating VARCHAR(20),
    rating_mpaa VARCHAR(10),
    budget_value JSON,
    fees_world JSON,
    trailer JSON,
    type VARCHAR(50) CHECK (type IN ('movie', 'series', 'cartoon', 'anime', 'animated-series', 'other'))
);

CREATE INDEX IF NOT EXISTS idx_media_type ON media(type);
CREATE INDEX IF NOT EXISTS idx_media_release_year ON media(release_year);

CREATE TABLE IF NOT EXISTS sequels (
    connection_id SERIAL PRIMARY KEY,
    type VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS connected_media (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    parent_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    connection_id INT REFERENCES sequels(connection_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, parent_id, connection_id)
);

CREATE TABLE IF NOT EXISTS genre (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS media_genre (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, genre_id)
);

CREATE TABLE IF NOT EXISTS country (
    country_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS media_country (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    country_id INT REFERENCES country(country_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, country_id)
);

CREATE TABLE IF NOT EXISTS person (
    person_id SERIAL PRIMARY KEY,
    ru_name VARCHAR(255),
    en_name VARCHAR(255),
    birth_date DATE,
    photo_url TEXT
);

CREATE TABLE IF NOT EXISTS role (
    role_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS media_person_role (
    id SERIAL PRIMARY KEY,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    person_id INT REFERENCES person(person_id) ON DELETE CASCADE,
    role_id INT REFERENCES role(role_id) ON DELETE CASCADE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS season (
    season_id SERIAL PRIMARY KEY,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    season_number INT NOT NULL,
    release_year INT,
    UNIQUE(media_id, season_number)
);

CREATE INDEX IF NOT EXISTS idx_season_media_id ON season(media_id);

CREATE TABLE IF NOT EXISTS episode (
    episode_id SERIAL PRIMARY KEY,
    season_id INT REFERENCES season(season_id) ON DELETE CASCADE,
    episode_number INT NOT NULL,
    title VARCHAR(255),
    release_date DATE,
    description TEXT,
    UNIQUE(season_id, episode_number)
);

CREATE INDEX IF NOT EXISTS idx_episode_season_id ON episode(season_id);

CREATE TABLE IF NOT EXISTS review (
    review_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES user_account(user_id) ON DELETE CASCADE,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    rating INT CHECK (rating BETWEEN 1 AND 10),
    comment_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_review_media_id ON review(media_id);
CREATE INDEX IF NOT EXISTS idx_review_user_id ON review(user_id);

CREATE TABLE IF NOT EXISTS user_list (
    list_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES user_account(user_id) ON DELETE CASCADE,
    list_name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_list_media (
    list_id INT REFERENCES user_list(list_id) ON DELETE CASCADE,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    PRIMARY KEY (list_id, media_id)
);

CREATE INDEX IF NOT EXISTS idx_media_genre ON media_genre(genre_id);
CREATE INDEX IF NOT EXISTS idx_media_country ON media_country(country_id);
CREATE INDEX IF NOT EXISTS idx_media_person ON media_person_role(person_id);
CREATE INDEX IF NOT EXISTS idx_connected_media_parent ON connected_media(parent_id);
