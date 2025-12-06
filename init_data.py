#!/usr/bin/env python3
import os
import sys
import psycopg2
import boto3
from botocore.exceptions import ClientError


def init_postgres():
    print("Checking PostgreSQL...")
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            sslmode='require'
        )
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'movies'
            );
        """)
        
        if cursor.fetchone()[0]:
            cursor.execute("SELECT COUNT(*) FROM movies;")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"PostgreSQL OK ({count} movies)")
                cursor.close()
                conn.close()
                return True
        
        print("Creating tables...")
        
        cursor.execute("""
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
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id SERIAL PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                results_count INTEGER NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        print("Inserting movies...")
        
        movies = [
            (1, "The Shawshank Redemption", 1994, 9.3, "Drama", "Frank Darabont", 
             "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.", "shawshank.jpg"),
            (2, "The Godfather", 1972, 9.2, "Crime, Drama", "Francis Ford Coppola",
             "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.", "godfather.jpg"),
            (3, "The Dark Knight", 2008, 9.0, "Action, Crime, Drama", "Christopher Nolan",
             "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.", "dark_knight.jpg"),
            (4, "Schindler's List", 1993, 8.9, "Biography, Drama, History", "Steven Spielberg",
             "In German-occupied Poland during World War II, industrialist Oskar Schindler gradually becomes concerned for his Jewish workforce after witnessing their persecution.", "schindlers_list.jpg"),
            (5, "The Lord of the Rings: The Return of the King", 2003, 8.9, "Adventure, Drama, Fantasy", "Peter Jackson",
             "Gandalf and Aragorn lead the World of Men against Sauron's army to draw his gaze from Frodo and Sam as they approach Mount Doom with the One Ring.", "lotr_return.jpg"),
            (6, "Pulp Fiction", 1994, 8.8, "Crime, Drama", "Quentin Tarantino",
             "The lives of two mob hitmen, a boxer, a gangster and his wife intertwine in four tales of violence and redemption.", "pulp_fiction.jpg"),
            (7, "Fight Club", 1999, 8.8, "Drama", "David Fincher",
             "An insomniac office worker and a devil-may-care soap maker form an underground fight club that evolves into much more.", "fight_club.jpg"),
            (8, "Forrest Gump", 1994, 8.8, "Drama, Romance", "Robert Zemeckis",
             "The presidencies of Kennedy and Johnson, the Vietnam War, and other historical events unfold from the perspective of an Alabama man.", "forrest_gump.jpg"),
            (9, "Inception", 2010, 8.8, "Action, Sci-Fi, Thriller", "Christopher Nolan",
             "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.", "inception.jpg"),
            (10, "Star Wars: Episode V", 1980, 8.7, "Action, Adventure, Fantasy", "Irvin Kershner",
             "After the Rebels are brutally overpowered by the Empire on the ice planet Hoth, Luke Skywalker begins Jedi training.", "star_wars_v.jpg"),
            (11, "The Matrix", 1999, 8.7, "Action, Sci-Fi", "Lana Wachowski, Lilly Wachowski",
             "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.", "matrix.jpg"),
            (12, "Goodfellas", 1990, 8.7, "Biography, Crime, Drama", "Martin Scorsese",
             "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen Hill and his mob partners.", "goodfellas.jpg"),
            (13, "The Green Mile", 1999, 8.6, "Crime, Drama, Fantasy", "Frank Darabont",
             "The lives of guards on Death Row are affected by one of their charges: a black man accused of child murder and rape, yet who has a mysterious gift.", "green_mile.jpg"),
            (14, "Interstellar", 2014, 8.6, "Adventure, Drama, Sci-Fi", "Christopher Nolan",
             "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.", "interstellar.jpg"),
            (15, "The Silence of the Lambs", 1991, 8.6, "Crime, Drama, Thriller", "Jonathan Demme",
             "A young F.B.I. cadet must receive the help of an incarcerated and manipulative cannibal killer to help catch another serial killer.", "silence_lambs.jpg"),
            (16, "Saving Private Ryan", 1998, 8.6, "Drama, War", "Steven Spielberg",
             "Following the Normandy Landings, a group of U.S. soldiers go behind enemy lines to retrieve a paratrooper.", "saving_ryan.jpg"),
            (17, "Parasite", 2019, 8.6, "Comedy, Drama, Thriller", "Bong Joon Ho",
             "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.", "parasite.jpg"),
            (18, "Gladiator", 2000, 8.5, "Action, Adventure, Drama", "Ridley Scott",
             "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery.", "gladiator.jpg"),
            (19, "The Departed", 2006, 8.5, "Crime, Drama, Thriller", "Martin Scorsese",
             "An undercover cop and a mole in the police attempt to identify each other while infiltrating an Irish gang in South Boston.", "departed.jpg"),
            (20, "Whiplash", 2014, 8.5, "Drama, Music", "Damien Chazelle",
             "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing.", "whiplash.jpg"),
        ]
        
        cursor.executemany("""
            INSERT INTO movies (id, title, year, rating, genre, director, description, poster_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, movies)
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM movies;")
        total = cursor.fetchone()[0]
        
        print(f"PostgreSQL OK ({total} movies)")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"PostgreSQL error: {e}")
        return False


def init_s3():
    print("Checking S3...")
    
    try:
        bucket_name = os.getenv('S3_BUCKET_NAME')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not bucket_name:
            print("S3_BUCKET_NAME not set, skipping")
            return False
        
        s3 = boto3.client('s3', region_name=region)
        
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"Bucket '{bucket_name}' not found, skipping")
            return False
        
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            if response.get('KeyCount', 0) > 0:
                print("S3 already has objects")
                return True
        except:
            pass
        
        posters_dir = '/app/posters'
        
        if os.path.exists(posters_dir) and os.listdir(posters_dir):
            print(f"Uploading real posters from {posters_dir}...")
            
            uploaded = 0
            for filename in os.listdir(posters_dir):
                if filename.endswith('.jpg'):
                    filepath = os.path.join(posters_dir, filename)
                    try:
                        with open(filepath, 'rb') as f:
                            s3.put_object(
                                Bucket=bucket_name,
                                Key=filename,
                                Body=f.read(),
                                ContentType='image/jpeg'
                            )
                        uploaded += 1
                        print(f"  {filename}")
                    except Exception as e:
                        print(f"  {filename} - error: {e}")
            
            print(f"S3 OK ({uploaded} posters)")
            return True
        else:
            print("Uploading placeholder posters...")
            
            import base64
            minimal_jpeg = base64.b64decode(
                '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a'
                'HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy'
                'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA'
                'AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEB'
                'AQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwABmQ/9k='
            )
            
            posters = [
                'shawshank.jpg', 'godfather.jpg', 'dark_knight.jpg', 'schindlers_list.jpg',
                'lotr_return.jpg', 'pulp_fiction.jpg', 'fight_club.jpg', 'forrest_gump.jpg',
                'inception.jpg', 'star_wars_v.jpg', 'matrix.jpg', 'goodfellas.jpg',
                'green_mile.jpg', 'interstellar.jpg', 'silence_lambs.jpg', 'saving_ryan.jpg',
                'parasite.jpg', 'gladiator.jpg', 'departed.jpg', 'whiplash.jpg'
            ]
            
            uploaded = 0
            for poster in posters:
                try:
                    s3.put_object(
                        Bucket=bucket_name,
                        Key=poster,
                        Body=minimal_jpeg,
                        ContentType='image/jpeg'
                    )
                    uploaded += 1
                except:
                    pass
            
            print(f"S3 OK ({uploaded} placeholders)")
            return True
        
    except Exception as e:
        print(f"S3 error: {e}")
        return False


def init_meilisearch():
    print("Checking Meilisearch...")
    
    try:
        import requests
        
        meili_host = os.getenv('MEILISEARCH_HOST', 'localhost')
        meili_port = os.getenv('MEILISEARCH_PORT', '7700')
        base_url = f"http://{meili_host}:{meili_port}"
        
        try:
            health = requests.get(f"{base_url}/health", timeout=5)
            if health.status_code != 200:
                print("Meilisearch not accessible, skipping")
                return False
        except:
            print("Meilisearch not accessible, skipping")
            return False
        
        try:
            stats = requests.get(f"{base_url}/indexes/movies/stats", timeout=5)
            if stats.status_code == 200:
                doc_count = stats.json().get('numberOfDocuments', 0)
                if doc_count > 0:
                    print(f"Meilisearch OK ({doc_count} documents)")
                    return True
        except:
            pass
        
        print("Fetching movies from database...")
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            sslmode='require'
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, poster_filename, year, rating, genre, director
            FROM movies
            ORDER BY id;
        """)
        
        rows = cursor.fetchall()
        
        movies = []
        for row in rows:
            movies.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'poster_filename': row[3],
                'year': row[4],
                'rating': float(row[5]),
                'genre': row[6],
                'director': row[7]
            })
        
        cursor.close()
        conn.close()
        
        if not movies:
            print("No movies found")
            return False
        
        print(f"Indexing {len(movies)} movies...")
        
        requests.post(
            f"{base_url}/indexes",
            json={"uid": "movies", "primaryKey": "id"},
            timeout=10
        )
        
        requests.put(
            f"{base_url}/indexes/movies/settings/searchable-attributes",
            json=["title", "description", "director", "genre"],
            timeout=10
        )
        
        response = requests.post(
            f"{base_url}/indexes/movies/documents",
            json=movies,
            timeout=30
        )
        
        if response.status_code in [200, 202]:
            print(f"Meilisearch OK ({len(movies)} movies)")
            return True
        else:
            print(f"Meilisearch indexing returned {response.status_code}")
            return False
        
    except Exception as e:
        print(f"Meilisearch error: {e}")
        return False


def main():
    print("\nData Initialization\n")
    
    if not init_postgres():
        print("PostgreSQL initialization failed - CRITICAL")
        sys.exit(1)
    
    init_s3()
    init_meilisearch()
    
    print("\nInitialization complete\n")


if __name__ == '__main__':
    main()