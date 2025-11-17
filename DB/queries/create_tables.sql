CREATE TABLE subscription_type IF NOT EXISTS (
    subscription_type_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE user_account IF NOT EXISTS (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    registration_date DATE DEFAULT CURRENT_DATE,
    subscription_type_id INT REFERENCES subscription_type(subscription_type_id),
    subscription_expiry_date DATE
);

CREATE TABLE media IF NOT EXISTS (
    media_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    ru_title VARCHAR(255),
    en_title VARCHAR(255),
    original_title VARCHAR(255),
    description TEXT,
    short_description TEXT,
    slogan TEXT,
    release_year INT,
    duration INT,
    posterUrl TEXT,
    posterUrlPreview TEXT,
    coverUrl TEXT,
    logoUrl TEXT,
    age_rating VARCHAR(20),
    rating_mpaa VARCHAR(10),
    budget_value VARCHAR(100),
    fees_world VARCHAR(100),
    type VARCHAR(50) CHECK (type IN ('movie', 'series', 'cartoon', 'anime', 'other'))
);

CREATE INDEX idx_media_type ON media(type);
CREATE INDEX idx_media_release_year ON media(release_year);

CREATE TABLE sequels IF NOT EXISTS (
    connection_id SERIAL PRIMARY KEY,
    type VARCHAR(50)
);

CREATE TABLE connected_media IF NOT EXISTS (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    parent_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    connection_id INT REFERENCES sequels(connection_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, parent_id, connection_id)
);

CREATE TABLE genre IF NOT EXISTS (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE country IF NOT EXISTS (
    country_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE media_genre IF NOT EXISTS (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, genre_id)
);

CREATE TABLE media_country IF NOT EXISTS (
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    country_id INT REFERENCES country(country_id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, country_id)
);

CREATE TABLE person IF NOT EXISTS (
    person_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    birth_date DATE,
    bio TEXT
);

CREATE TABLE role IF NOT EXISTS (
    role_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE media_person_role IF NOT EXISTS (
    id SERIAL PRIMARY KEY,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    person_id INT REFERENCES person(person_id) ON DELETE CASCADE,
    role_id INT REFERENCES role(role_id) ON DELETE CASCADE
);

CREATE TABLE season IF NOT EXISTS (
    season_id SERIAL PRIMARY KEY,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    season_number INT NOT NULL,
    title VARCHAR(255)
);

CREATE INDEX idx_season_media_id ON season(media_id);

CREATE TABLE episode IF NOT EXISTS (
    episode_id SERIAL PRIMARY KEY,
    season_id INT REFERENCES season(season_id) ON DELETE CASCADE,
    episode_number INT NOT NULL,
    title VARCHAR(255),
    duration INT,
    description TEXT
);

CREATE INDEX idx_episode_season_id ON episode(season_id);

CREATE TABLE review IF NOT EXISTS (
    review_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES user_account(user_id) ON DELETE CASCADE,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    rating INT CHECK (rating BETWEEN 1 AND 10),
    comment_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_media_id ON review(media_id);
CREATE INDEX idx_review_user_id ON review(user_id);

CREATE TABLE user_list IF NOT EXISTS (
    list_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES user_account(user_id) ON DELETE CASCADE,
    list_name VARCHAR(255) NOT NULL
);

CREATE TABLE user_list_media IF NOT EXISTS (
    list_id INT REFERENCES user_list(list_id) ON DELETE CASCADE,
    media_id INT REFERENCES media(media_id) ON DELETE CASCADE,
    PRIMARY KEY (list_id, media_id)
);


CREATE INDEX idx_media_genre ON media_genre(genre_id);
CREATE INDEX idx_media_country ON media_country(country_id);
CREATE INDEX idx_media_person ON media_person_role(person_id);
CREATE INDEX idx_connected_media_parent ON connected_media(parent_id);
