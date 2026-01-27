#!/usr/bin/env python3
import json
import os

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
    )


def ensure_movies_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS movies (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            year INTEGER NOT NULL,
            rating DECIMAL(3, 1) NOT NULL,
            genre VARCHAR(255) NOT NULL,
            director VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            poster_filename VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def load_movies_from_file():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "data", "movies.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_movies():
    movies = load_movies_from_file()

    conn = get_db_connection()
    cursor = conn.cursor()

    ensure_movies_table(cursor)

    for movie in movies:
        cursor.execute(
            """
            INSERT INTO movies (id, title, year, rating, genre, director, description, poster_filename)
            VALUES (%(id)s, %(title)s, %(year)s, %(rating)s, %(genre)s, %(director)s, %(description)s, %(poster_filename)s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                year = EXCLUDED.year,
                rating = EXCLUDED.rating,
                genre = EXCLUDED.genre,
                director = EXCLUDED.director,
                description = EXCLUDED.description,
                poster_filename = EXCLUDED.poster_filename;
            """,
            movie,
        )

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    sync_movies()

