BEGIN;
SET LOCAL search_path = public, pg_catalog;

CREATE TYPE "age_rating_enum" AS ENUM ('0+', '6+', '12+', '16+', '18+');
CREATE TYPE "mpaa_rating_enum" AS ENUM ('G', 'PG', 'PG-13', 'R', 'NC-17');

CREATE TABLE "subscription_type" (
  "subscription_type_id" serial NOT NULL,
  "name" varchar(100) NOT NULL,
  "description" text,
  CONSTRAINT "subscription_type_pkey" PRIMARY KEY (subscription_type_id),
  CONSTRAINT "uq_subscription_type_name" UNIQUE (name)
);

CREATE TABLE "user_account" (
  "user_id" serial NOT NULL,
  "email" varchar(255) NOT NULL,
  "password_hash" varchar(255) NOT NULL,
  "full_name" varchar(255),
  "registration_date" date NOT NULL DEFAULT CURRENT_DATE,
  "subscription_type_id" integer,
  "subscription_expiry_date" date,
  CONSTRAINT "user_account_email_key" UNIQUE (email),
  CONSTRAINT "user_account_pkey" PRIMARY KEY (user_id)
);

CREATE INDEX "idx_user_account_subscription_type_id" ON "user_account" (subscription_type_id);

CREATE TABLE "review" (
  "review_id" serial NOT NULL,
  "user_id" integer NOT NULL,
  "media_id" integer NOT NULL,
  "rating" integer,
  "comment_text" text,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "review_pkey" PRIMARY KEY (review_id),
  CONSTRAINT "review_rating_check" CHECK (rating BETWEEN 1 AND 10)
);

CREATE INDEX "idx_review_media_id" ON "review" (media_id);

CREATE INDEX "idx_review_user_id" ON "review" (user_id);

CREATE TABLE "user_list" (
  "list_id" serial NOT NULL,
  "user_id" integer NOT NULL,
  "list_name" varchar(255) NOT NULL,
  CONSTRAINT "user_list_pkey" PRIMARY KEY (list_id)
);

CREATE INDEX "idx_user_list_user_id" ON "user_list" (user_id);

CREATE TABLE "user_list_media" (
  "list_id" integer NOT NULL,
  "media_id" integer NOT NULL,
  CONSTRAINT "user_list_media_pkey" PRIMARY KEY (list_id, media_id)
);

CREATE INDEX "idx_user_list_media_media_id" ON "user_list_media" (media_id);

CREATE TABLE "country" (
  "country_id" serial NOT NULL,
  "name" varchar(100) NOT NULL,
  CONSTRAINT "country_name_key" UNIQUE (name),
  CONSTRAINT "country_pkey" PRIMARY KEY (country_id)
);

CREATE TABLE "media_country" (
  "media_id" integer NOT NULL,
  "country_id" integer NOT NULL,
  CONSTRAINT "media_country_pkey" PRIMARY KEY (media_id, country_id)
);

CREATE INDEX "idx_media_country" ON "media_country" (country_id);

CREATE TABLE "genre" (
  "genre_id" serial NOT NULL,
  "name" varchar(100) NOT NULL,
  CONSTRAINT "genre_name_key" UNIQUE (name),
  CONSTRAINT "genre_pkey" PRIMARY KEY (genre_id)
);

CREATE TABLE "media_genre" (
  "media_id" integer NOT NULL,
  "genre_id" integer NOT NULL,
  CONSTRAINT "media_genre_pkey" PRIMARY KEY (media_id, genre_id)
);

CREATE INDEX "idx_media_genre" ON "media_genre" (genre_id);

CREATE TABLE "media" (
  "media_id" serial NOT NULL,
  "imdb_id" varchar(50),
  "title" varchar(255) NOT NULL,
  "rating" double precision,
  "votes" integer,
  "en_title" varchar(255),
  "description" text,
  "short_description" text,
  "slogan" text,
  "release_year" integer,
  "duration" integer,
  "posterurl" text,
  "posterurlpreview" text,
  "logourl" text,
  "age_rating" age_rating_enum,
  "rating_mpaa" mpaa_rating_enum,
  "budget_value" json,
  "fees_world" json,
  "trailer" json,
  "type" varchar(50),
  CONSTRAINT "media_pkey" PRIMARY KEY (media_id),
  CONSTRAINT "media_type_check" CHECK (type IN ('movie', 'series', 'cartoon', 'anime', 'animated-series', 'other'))
);

CREATE INDEX "idx_media_release_year" ON "media" (release_year);

CREATE INDEX "idx_media_type" ON "media" (type);

CREATE TABLE "person" (
  "person_id" serial NOT NULL,
  "ru_name" varchar(255),
  "en_name" varchar(255),
  "birth_date" date,
  "photo_url" text,
  CONSTRAINT "person_pkey" PRIMARY KEY (person_id)
);

CREATE TABLE "role" (
  "role_id" serial NOT NULL,
  "name" varchar(100) NOT NULL,
  CONSTRAINT "role_pkey" PRIMARY KEY (role_id),
  CONSTRAINT "uq_role_name" UNIQUE (name)
);

CREATE TABLE "media_person_role" (
  "id" serial NOT NULL,
  "media_id" integer NOT NULL,
  "person_id" integer NOT NULL,
  "role_id" integer NOT NULL,
  "description" text,
  CONSTRAINT "media_person_role_pkey" PRIMARY KEY (id),
  CONSTRAINT "uq_media_person_role" UNIQUE (media_id, person_id, role_id)
);

CREATE INDEX "idx_media_person" ON "media_person_role" (person_id);

CREATE INDEX "idx_media_person_role_role_id" ON "media_person_role" (role_id);

CREATE TABLE "connection_type" (
  "connection_type_id" serial NOT NULL,
  "name" varchar(100) NOT NULL,
  CONSTRAINT "connection_type_pkey" PRIMARY KEY (connection_type_id),
  CONSTRAINT "connection_type_name_key" UNIQUE (name)
);

CREATE TABLE "connected_media" (
  "media_id" integer NOT NULL,
  "parent_id" integer NOT NULL,
  "connection_id" integer NOT NULL,
  CONSTRAINT "connected_media_pkey" PRIMARY KEY (media_id, parent_id, connection_id),
  CONSTRAINT "chk_connected_media_not_self" CHECK (media_id <> parent_id)
);

CREATE INDEX "idx_connected_media_parent" ON "connected_media" (parent_id);

CREATE INDEX "idx_connected_media_connection_id" ON "connected_media" (connection_id);

CREATE TABLE "season" (
  "season_id" serial NOT NULL,
  "media_id" integer NOT NULL,
  "season_number" integer NOT NULL,
  "release_year" integer,
  CONSTRAINT "season_media_id_season_number_key" UNIQUE (media_id, season_number),
  CONSTRAINT "season_pkey" PRIMARY KEY (season_id)
);

CREATE INDEX "idx_season_media_id" ON "season" (media_id);

CREATE TABLE "episode" (
  "episode_id" serial NOT NULL,
  "season_id" integer NOT NULL,
  "episode_number" integer NOT NULL,
  "title" varchar(255),
  "release_date" date,
  "description" text,
  CONSTRAINT "episode_pkey" PRIMARY KEY (episode_id),
  CONSTRAINT "episode_season_id_episode_number_key" UNIQUE (season_id, episode_number)
);

CREATE INDEX "idx_episode_season_id" ON "episode" (season_id);

ALTER TABLE "user_account" ADD CONSTRAINT "user_account_subscription_type_id_fkey" FOREIGN KEY (subscription_type_id) REFERENCES subscription_type(subscription_type_id);

ALTER TABLE "review" ADD CONSTRAINT "review_user_id_fkey" FOREIGN KEY (user_id) REFERENCES user_account(user_id) ON DELETE CASCADE;

ALTER TABLE "review" ADD CONSTRAINT "fk_review_media_id" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "user_list" ADD CONSTRAINT "user_list_user_id_fkey" FOREIGN KEY (user_id) REFERENCES user_account(user_id) ON DELETE CASCADE;

ALTER TABLE "user_list_media" ADD CONSTRAINT "user_list_media_list_id_fkey" FOREIGN KEY (list_id) REFERENCES user_list(list_id) ON DELETE CASCADE;

ALTER TABLE "user_list_media" ADD CONSTRAINT "fk_user_list_media_media_id" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "media_country" ADD CONSTRAINT "media_country_country_id_fkey" FOREIGN KEY (country_id) REFERENCES country(country_id) ON DELETE CASCADE;

ALTER TABLE "media_country" ADD CONSTRAINT "media_country_media_id_fkey" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "media_genre" ADD CONSTRAINT "media_genre_genre_id_fkey" FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE;

ALTER TABLE "media_genre" ADD CONSTRAINT "media_genre_media_id_fkey" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "media_person_role" ADD CONSTRAINT "media_person_role_media_id_fkey" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "media_person_role" ADD CONSTRAINT "media_person_role_person_id_fkey" FOREIGN KEY (person_id) REFERENCES person(person_id) ON DELETE CASCADE;

ALTER TABLE "media_person_role" ADD CONSTRAINT "media_person_role_role_id_fkey" FOREIGN KEY (role_id) REFERENCES role(role_id) ON DELETE CASCADE;

ALTER TABLE "connected_media" ADD CONSTRAINT "connected_media_connection_id_fkey" FOREIGN KEY (connection_id) REFERENCES connection_type(connection_type_id) ON DELETE CASCADE;

ALTER TABLE "connected_media" ADD CONSTRAINT "fk_connected_media_media_id" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "connected_media" ADD CONSTRAINT "fk_connected_media_parent_id" FOREIGN KEY (parent_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "season" ADD CONSTRAINT "season_media_id_fkey" FOREIGN KEY (media_id) REFERENCES media(media_id) ON DELETE CASCADE;

ALTER TABLE "episode" ADD CONSTRAINT "episode_season_id_fkey" FOREIGN KEY (season_id) REFERENCES season(season_id) ON DELETE CASCADE;

COMMIT;
