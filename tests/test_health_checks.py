import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_health_check_structure():
    from services.s3_check import check_s3
    
    # Mock environment variables
    os.environ['S3_BUCKET_NAME'] = 'test-bucket'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # This will fail connection but should return proper structure
    result = check_s3()
    
    assert 'status' in result
    assert 'service' in result
    assert 'message' in result
    assert result['service'] == 's3'
    assert result['status'] in ['healthy', 'unhealthy']