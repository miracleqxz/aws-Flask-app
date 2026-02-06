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
            'matchingStrategy': 'all'
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
                'genres': hit.get('genres', []),
                'director': hit.get('director')
            })

        return movies

    except Exception as e:
        print(f"Meilisearch search error: {e}")
        return []


def search_movies_by_genre(genre, limit=20):
    try:
        client = get_meili_client()
        index = client.get_index('movies')

        results = index.search('', {
            'limit': limit,
            'filter': f'genres = "{genre}"',
            'sort': ['rating:desc']
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
                'genres': hit.get('genres', []),
                'director': hit.get('director')
            })

        return movies

    except Exception as e:
        print(f"Meilisearch genre search error: {e}")
        return []


def index_all_movies():
    from database.postgres import get_all_movies

    try:
        client = get_meili_client()
        try:
            client.create_index('movies', {'primaryKey': 'id'})
        except Exception:
            pass

        index = client.index('movies')

        index.update_settings({
            'searchableAttributes': [
                'title',
                'director',
                'description',
                'genres'
            ],

            'filterableAttributes': ['genres', 'year', 'rating', 'director'],
            'sortableAttributes': ['year', 'rating', 'title'],

            'rankingRules': [
                'words',
                'typo',
                'proximity',
                'attribute',
                'sort',
                'exactness'
            ],

            'typoTolerance': {
                'enabled': True,
                'minWordSizeForTypos': {
                    'oneTypo': 4,
                    'twoTypos': 8
                }
            },

            'stopWords': [
                'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was',
                'are', 'were', 'been', 'be', 'have', 'has', 'had',
                'it', 'its', 'this', 'that', 'i', 'you', 'he', 'she',
                'we', 'they', 'what', 'which', 'who', 'where', 'when'
            ],

            'synonyms': {
                'film': ['movie'],
                'movie': ['film'],
                'scary': ['horror', 'thriller'],
                'horror': ['scary', 'thriller'],
                'funny': ['comedy'],
                'comedy': ['funny'],
                'sci-fi': ['science fiction', 'scifi'],
                'scifi': ['science fiction', 'sci-fi'],
                'crime': ['gangster', 'mafia'],
                'gangster': ['crime', 'mafia']
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
