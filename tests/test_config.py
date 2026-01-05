import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config


def test_config_defaults():
    assert Config.FLASK_HOST == '0.0.0.0'
    assert Config.FLASK_PORT == 5000
    assert Config.AWS_REGION == 'us-east-1'
    

def test_config_redis():
    assert hasattr(Config, 'REDIS_HOST')
    assert hasattr(Config, 'REDIS_PORT')
    assert Config.REDIS_PORT == 6379


def test_config_postgres():
    assert hasattr(Config, 'POSTGRES_HOST')
    assert hasattr(Config, 'POSTGRES_PORT')
    assert hasattr(Config, 'POSTGRES_DB')