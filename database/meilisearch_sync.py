import meilisearch
from config import Config


def get_meili_client():
    return meilisearch.Client(
        f'http://{Config.MEILISEARCH_HOST}:{Config.MEILISEARCH_PORT}',
        Config.MEILISEARCH_KEY
    )


def search_movies_meili(query, limit=20):
    try:
        client = get_meili_client()
        index = client.index('movies')
        
        results = index.search(query, {
            'limit': limit,
            'attributesToRetrieve': ['id', 'title', 'year', 'genre', 'rating', 'poster_url']
        })
        
        return results['hits']
        
    except Exception as e:
        print(f"Meilisearch error: {e}")
        return []


def index_all_movies():
    from database.movies_db import get_all_movies
    
    try:
        client = get_meili_client()
        try:
            client.create_index('movies', {'primaryKey': 'id'})
        except:
            pass  # Index already exists
        
        index = client.index('movies')
        
        # Configure searchable attributes
        index.update_settings({
            'searchableAttributes': ['title', 'genre', 'year'],
            'filterableAttributes': ['genre', 'year', 'rating'],
            'sortableAttributes': ['year', 'rating', 'title']
        })
        
        
        movies = get_all_movies()
        
        # Convert to list of dicts
        movies_list = [dict(movie) for movie in movies]
        
        # Index in Meilisearch
        index.add_documents(movies_list)
        
        print(f"Indexed {len(movies_list)} movies to Meilisearch")
        return True
        
    except Exception as e:
        print(f"Indexing error: {e}")
        return False