import meilisearch
from config import Config


def get_meili_client():
    api_key = Config.MEILISEARCH_KEY if Config.MEILISEARCH_KEY else None
    
    return meilisearch.Client(
        f'http://{Config.MEILISEARCH_HOST}:{Config.MEILISEARCH_PORT}',
        api_key
    )


def search_movies_meili(query, limit=20):
    try:
        client = get_meili_client()
        index = client.get_index('movies')
        
        results = index.search(query, {
            'limit': limit,
            'matchingStrategy': 'last'  
        })
        
        movies = []
        for hit in results.get('hits', []):
            movies.append({
                'id': hit.get('id'),
                'title': hit.get('title'),
                'description': hit.get('description'),
                'poster_filename': hit.get('poster_filename'),  
                'year': hit.get('year'),
                'rating': hit.get('rating'),
                'genre': hit.get('genre'),
                'director': hit.get('director')
            })
        
        return movies
        
    except Exception as e:
        print(f"Meilisearch search error: {e}")
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
        
        index.update_settings({
            # Priority order for searching
            'searchableAttributes': [
                'title',
                'director',
                'description',
                'genre'
            ],
            
            'filterableAttributes': ['genre', 'year', 'rating'],
            'sortableAttributes': ['year', 'rating', 'title'],
            
            
            'rankingRules': [
                'words',
                'typo',
                'proximity',
                'attribute',
                'sort',
                'exactness'
            ],
            
            # Typo tolerance - finds misspelled words
            'typoTolerance': {
                'enabled': True,
                'minWordSizeForTypos': {
                    'oneTypo': 3,   # 1 typo allowed for 3+ char words
                    'twoTypos': 6  # 2 typos allowed for 6+ char words
                }
            },
            
           
            'stopWords': [
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are',
                'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does',
                'did', 'will', 'would', 'could', 'should', 'it', 'its',
                'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
                'we', 'they', 'what', 'which', 'who', 'where', 'when', 'how'
            ],
            
            
            'synonyms': {
                'film': ['movie', 'picture'],
                'movie': ['film', 'picture'],
                'scary': ['horror', 'thriller'],
                'horror': ['scary', 'thriller'],
                'funny': ['comedy', 'humor'],
                'comedy': ['funny', 'humor'],
                'action': ['adventure', 'thriller'],
                'romantic': ['romance', 'love'],
                'romance': ['romantic', 'love'],
                'sci-fi': ['science fiction', 'scifi'],
                'scifi': ['science fiction', 'sci-fi'],
                'science fiction': ['sci-fi', 'scifi'],
                'crime': ['gangster', 'mafia', 'noir'],
                'gangster': ['crime', 'mafia'],
                'war': ['military', 'battle'],
                'animated': ['animation', 'cartoon'],
                'animation': ['animated', 'cartoon'],
                'documentary': ['doc', 'docu'],
                'biography': ['biopic', 'bio']
            }
        })
        
        movies = get_all_movies()
        movies_list = [dict(movie) for movie in movies]
        
        index.add_documents(movies_list)
        
        print(f"Indexed {len(movies_list)} movies to Meilisearch")
        return True
        
    except Exception as e:
        print(f"Indexing error: {e}")
        return False
