#!/usr/bin/env python3
import json
import os
import sys

import boto3
import psycopg2
from botocore.exceptions import ClientError


def init_postgres():
    print("Checking PostgreSQL...")
    
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            sslmode="require",
        )
        
        cursor = conn.cursor()
        
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

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS search_queries (
                id SERIAL PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                results_count INTEGER NOT NULL,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        print("Syncing movies from data/movies.json ...")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(base_dir, "data", "movies.json")

        with open(data_path, "r", encoding="utf-8") as f:
            movies = json.load(f)

        values = [
            (
                m["id"],
                m["title"],
                m["year"],
                m["rating"],
                m["genre"],
                m["director"],
                m["description"],
                m["poster_filename"],
            )
            for m in movies
        ]

        cursor.executemany(
            """
            INSERT INTO movies (id, title, year, rating, genre, director, description, poster_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                year = EXCLUDED.year,
                rating = EXCLUDED.rating,
                genre = EXCLUDED.genre,
                director = EXCLUDED.director,
                description = EXCLUDED.description,
                poster_filename = EXCLUDED.poster_filename;
            """,
            values,
        )

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
        
        
    except Exception as e:
        print(f"S3 error: {e}")
        return False


def init_meilisearch():
    print("Checking Meilisearch...")
    
    try:
        import requests

        meili_host = os.getenv("MEILISEARCH_HOST", "localhost")
        meili_port = os.getenv("MEILISEARCH_PORT", "7700")
        base_url = f"http://{meili_host}:{meili_port}"

        try:
            health = requests.get(f"{base_url}/health", timeout=5)
            if health.status_code != 200:
                print("Meilisearch not accessible, skipping")
                return False
        except:
            print("Meilisearch not accessible, skipping")
            return False

        existing_ids = set()
        index_exists = False

        try:
            stats = requests.get(f"{base_url}/indexes/movies/stats", timeout=5)
            if stats.status_code == 200:
                index_exists = True
                doc_count = stats.json().get("numberOfDocuments", 0)
                print(f"Meilisearch movies index currently has {doc_count} documents")
        except:
            pass

        if index_exists:
            limit = 1000
            offset = 0
            while True:
                try:
                    resp = requests.get(
                        f"{base_url}/indexes/movies/documents",
                        params={"fields": "id", "limit": limit, "offset": offset},
                        timeout=10,
                    )
                    if resp.status_code != 200:
                        break

                    payload = resp.json()
                    if isinstance(payload, dict) and "results" in payload:
                        docs = payload["results"]
                    else:
                        docs = payload

                    if not docs:
                        break

                    for doc in docs:
                        if "id" in doc:
                            existing_ids.add(doc["id"])

                    if len(docs) < limit:
                        break
                    offset += limit
                except Exception:
                    break

        print("Fetching movies from database...")

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            sslmode="require",
        )

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, poster_filename, year, rating, genre, director
            FROM movies
            ORDER BY id;
            """
        )

        rows = cursor.fetchall()

        movies = []
        for row in rows:
            movies.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "poster_filename": row[3],
                    "year": row[4],
                    "rating": float(row[5]),
                    "genre": row[6],
                    "director": row[7],
                }
            )

        cursor.close()
        conn.close()

        if not movies:
            print("No movies found")
            return False

        missing_movies = [m for m in movies if m["id"] not in existing_ids]

        if not index_exists:
            requests.post(
                f"{base_url}/indexes",
                json={"uid": "movies", "primaryKey": "id"},
                timeout=10,
            )

            requests.put(
                f"{base_url}/indexes/movies/settings/searchable-attributes",
                json=["title", "description", "director", "genre"],
                timeout=10,
            )

        if not missing_movies:
            print("Meilisearch index is up to date")
            return True

        print(f"Indexing {len(missing_movies)} new movies...")

        response = requests.post(
            f"{base_url}/indexes/movies/documents",
            json=missing_movies,
            timeout=30,
        )

        if response.status_code in [200, 202]:
            print(f"Meilisearch OK ({len(missing_movies)} movies indexed)")
            return True

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