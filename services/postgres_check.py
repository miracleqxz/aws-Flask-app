
import psycopg2
from config import Config


def check_postgres():
    try:
        conn = psycopg2.connect(
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT,
            database=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD,
            connect_timeout=5,
            sslmode='require'
        )

        cursor = conn.cursor()


        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
        db_size = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public';
        """)
        tables_count = cursor.fetchone()[0]

        # Active connections
        cursor.execute("""
            SELECT count(*) FROM pg_stat_activity
            WHERE state = 'active';
        """)
        active_connections = cursor.fetchone()[0]

        # Total connections
        cursor.execute("SELECT count(*) FROM pg_stat_activity;")
        total_connections = cursor.fetchone()[0]

        # Max connections
        cursor.execute("SHOW max_connections;")
        max_connections = cursor.fetchone()[0]

        # Uptime
        cursor.execute("SELECT date_trunc('second', current_timestamp - pg_postmaster_start_time());")
        uptime = str(cursor.fetchone()[0])

        # Transaction stats
        cursor.execute("""
            SELECT
                xact_commit,
                xact_rollback,
                blks_read,
                blks_hit
            FROM pg_stat_database
            WHERE datname = current_database();
        """)
        stats = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            'status': 'healthy',
            'service': 'postgresql',
            'message': 'Successfully connected to PostgreSQL',
            'details': {
                'connection': {
                    'host': Config.POSTGRES_HOST,
                    'port': Config.POSTGRES_PORT,
                    'database': Config.POSTGRES_DB
                },
                'version': version.split()[1],
                'uptime': uptime,
                'connections': {
                    'active': active_connections,
                    'total': total_connections,
                    'max': int(max_connections),
                    'usage_percent': round((total_connections / int(max_connections)) * 100, 2)
                },
                'database': {
                    'size': db_size,
                    'tables_count': tables_count
                },
                'performance': {
                    'transactions_committed': stats[0],
                    'transactions_rolled_back': stats[1],
                    'blocks_read_from_disk': stats[2],
                    'blocks_hit_in_cache': stats[3],
                    'cache_hit_ratio': round((stats[3] / (stats[2] + stats[3])) * 100, 2) if (stats[2] + stats[3]) > 0 else 100
                }
            }
        }

    except psycopg2.OperationalError as e:
        return {
            'status': 'unhealthy',
            'service': 'postgresql',
            'message': f'Connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'service': 'postgresql',
            'message': f'Unexpected error: {str(e)}'
        }
