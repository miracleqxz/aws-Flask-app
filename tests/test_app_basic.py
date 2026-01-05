import pytest


def test_imports():
    try:
        import app
        import config
        import analytics_worker
        assert True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_database_modules():
    try:
        from database import s3_storage
        from database import meilisearch_sync
        from database import sqs_analytics
        assert True
    except ImportError as e:
        pytest.fail(f"Database module import failed: {e}")


def test_services_modules():
    try:
        from services import postgres_check
        from services import redis_check
        from services import s3_check
        assert True
    except ImportError as e:
        pytest.fail(f"Services module import failed: {e}")
