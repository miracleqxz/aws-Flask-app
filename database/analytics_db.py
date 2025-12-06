import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_db_connection():
    return psycopg2.connect(
        host=Config.POSTGRES_HOST,
        port=Config.POSTGRES_PORT,
        database=Config.POSTGRES_DB,
        user=Config.POSTGRES_USER,
        password=Config.POSTGRES_PASSWORD,
        sslmode='require'
    )


def save_search_analytics(query, results_count, cached):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO search_queries (query, results_count)
            VALUES (%s, %s)
        """, (query, results_count))
        
        conn.commit()
    except Exception as e:
        print(f"Error saving analytics: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def get_popular_searches(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT 
                query,
                COUNT(*) as search_count,
                AVG(results_count) as avg_results
            FROM search_queries
            WHERE searched_at > NOW() - INTERVAL '7 days'
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT %s
        """, (limit,))
        
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"Error getting popular searches: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_search_stats():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_searches,
                COUNT(DISTINCT query) as unique_queries,
                AVG(results_count) as avg_results_per_search
            FROM search_queries
            WHERE searched_at > NOW() - INTERVAL '7 days'
        """)
        
        stats = cursor.fetchone()
        return stats if stats else {
            'total_searches': 0,
            'unique_queries': 0,
            'avg_results_per_search': 0
        }
    except Exception as e:
        print(f"Error getting search stats: {e}")
        return {
            'total_searches': 0,
            'unique_queries': 0,
            'avg_results_per_search': 0
        }
    finally:
        cursor.close()
        conn.close()
