from database.movies_db import get_all_movies
from database.meilisearch_sync import index_movie_to_meili
import meilisearch
from config import Config


def index_all_movies_to_meili():
    print("Meilisearch - Movie Indexing")
    
    try:
        client = meilisearch.Client(
            f"http://{Config.MEILISEARCH_HOST}:{Config.MEILISEARCH_PORT}"
        )
        
        try:
            index = client.get_index('movies')
            print(f"Index 'movies' exists")
        except:
            index = client.create_index('movies', {'primaryKey': 'id'})
            print(f"Created index 'movies'")
        
        movies = get_all_movies()
        print(f"\nFound {len(movies)} movies in database")
        
        movies_data = []
        for movie in movies:
            movies_data.append({
                'id': movie['id'],
                'title': movie['title'],
                'year': movie['year'],
                'rating': float(movie['rating']),
                'genre': movie['genre'],
                'director': movie['director'],
                'description': movie['description']
            })
        
        # Batch index
        print("\nIndexing movies...")
        result = index.add_documents(movies_data)
        print(f"Indexed {len(movies_data)} movies")
        print(f"   Task UID: {result['taskUid']}")
        
        # Configure searchable attributes
        index.update_searchable_attributes([
            'title',
            'director',
            'genre',
            'description'
        ])
        
        print("\n" + "=" * 50)
        print("Indexing complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == '__main__':
    index_all_movies_to_meili()
