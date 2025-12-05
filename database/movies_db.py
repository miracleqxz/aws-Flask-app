
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_db_connection():
    return psycopg2.connect(
        host=Config.POSTGRES_HOST,
        port=Config.POSTGRES_PORT,
        database=Config.POSTGRES_DB,
        user=Config.POSTGRES_USER,
        password=Config.POSTGRES_PASSWORD
    )


def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        schema = f.read()
    
    
    cursor.execute(schema)
    conn.commit()
    
    cursor.close()
    conn.close()
    
    print("Database schema created!")


def insert_movie(movie_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO movies (title, year, rating, genre, director, description, poster_filename)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        movie_data['title'],
        movie_data['year'],
        movie_data['rating'],
        movie_data['genre'],
        movie_data['director'],
        movie_data['description'],
        movie_data['poster_filename']
    ))
    
    movie_id = cursor.fetchone()[0]
    conn.commit()
    
    cursor.close()
    conn.close()
    
    return movie_id


def get_all_movies():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, title, year, rating, genre, director, description, poster_filename
        FROM movies
        ORDER BY rating DESC
    """)
    
    movies = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return movies


def get_movie_by_id(movie_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, title, year, rating, genre, director, description, poster_filename
        FROM movies
        WHERE id = %s
    """, (movie_id,))
    
    movie = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return movie


def count_movies():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return count


def log_search_query(query, results_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO search_queries (query, results_count)
        VALUES (%s, %s)
    """, (query, results_count))
    
    conn.commit()
    
    cursor.close()
    conn.close()
