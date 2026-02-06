import pytest


def test_imports():
    try:
        import app  # noqa: F401
        import config  # noqa: F401
        import analytics_worker  # noqa: F401
        assert True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_database_modules():
    try:
        from database import s3_storage  # noqa: F401
        from database import meilisearch_sync  # noqa: F401
        from database import sqs_analytics  # noqa: F401
        assert True
    except ImportError as e:
        pytest.fail(f"Database module import failed: {e}")


