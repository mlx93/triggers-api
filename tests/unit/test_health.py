"""
Unit tests for GET /health Lambda handler.

Tests health endpoint with DynamoDB and S3 connectivity checks.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from src.handlers.health import determine_overall_status


@pytest.fixture
def mock_event():
    """Create a mock Lambda event."""
    return {
        'httpMethod': 'GET',
        'path': '/health',
        'headers': {},
        'queryStringParameters': None
    }


@pytest.fixture
def mock_context():
    """Create a mock Lambda context."""
    context = MagicMock()
    context.function_name = 'test-health'
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-health'
    return context


@pytest.fixture
def setup_aws_resources(monkeypatch):
    """Set up mock AWS resources (DynamoDB table and S3 bucket)."""
    with mock_aws():
        # Set environment variables before importing health module
        table_name = 'test-events-table'
        bucket_name = 'test-events-bucket'
        
        monkeypatch.setenv('EVENTS_TABLE', table_name)
        monkeypatch.setenv('EVENTS_BUCKET', bucket_name)
        monkeypatch.setenv('API_VERSION', '1.0.0')
        
        # Reload the health module to pick up new environment variables
        import importlib
        import src.handlers.health
        importlib.reload(src.handlers.health)
        
        # Create DynamoDB table
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'sk', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create S3 bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=bucket_name)
        
        yield
        
        # Reload module to restore original environment
        importlib.reload(src.handlers.health)


class TestHealthCheckFunctions:
    """Test health check helper functions."""
    
    def test_check_dynamodb_health_healthy(self, setup_aws_resources):
        """Test DynamoDB health check returns healthy status."""
        from src.handlers.health import check_dynamodb_health
        status, latency = check_dynamodb_health()
        assert status == "healthy"
        assert latency >= 0
    
    def test_check_dynamodb_health_table_not_found(self, setup_aws_resources, monkeypatch):
        """Test DynamoDB health check returns unhealthy when table not found."""
        from src.handlers.health import check_dynamodb_health
        import importlib
        import src.handlers.health
        monkeypatch.setenv('EVENTS_TABLE', 'nonexistent-table')
        importlib.reload(src.handlers.health)
        status, latency = check_dynamodb_health()
        assert status == "unhealthy"
        assert latency >= 0
    
    def test_check_s3_health_healthy(self, setup_aws_resources):
        """Test S3 health check returns healthy status."""
        from src.handlers.health import check_s3_health
        status, latency = check_s3_health()
        assert status == "healthy"
        assert latency >= 0
    
    def test_check_s3_health_bucket_not_found(self, setup_aws_resources, monkeypatch):
        """Test S3 health check returns unhealthy when bucket not found."""
        from src.handlers.health import check_s3_health
        import importlib
        import src.handlers.health
        monkeypatch.setenv('EVENTS_BUCKET', 'nonexistent-bucket')
        importlib.reload(src.handlers.health)
        status, latency = check_s3_health()
        assert status == "unhealthy"
        assert latency >= 0
    
    def test_determine_overall_status_healthy(self):
        """Test overall status determination when all dependencies healthy."""
        status = determine_overall_status("healthy", "healthy")
        assert status == "healthy"
    
    def test_determine_overall_status_degraded_s3(self):
        """Test overall status determination when S3 is degraded."""
        status = determine_overall_status("healthy", "degraded")
        assert status == "degraded"
    
    def test_determine_overall_status_degraded_dynamodb(self):
        """Test overall status determination when DynamoDB is degraded."""
        status = determine_overall_status("degraded", "healthy")
        assert status == "degraded"
    
    def test_determine_overall_status_unhealthy_dynamodb(self):
        """Test overall status determination when DynamoDB is unhealthy."""
        status = determine_overall_status("unhealthy", "healthy")
        assert status == "unhealthy"
    
    def test_determine_overall_status_unhealthy_s3_only(self):
        """Test overall status determination when only S3 is unhealthy (degraded)."""
        status = determine_overall_status("healthy", "unhealthy")
        assert status == "degraded"  # S3 failure is degraded, not unhealthy


class TestHealthEndpoint:
    """Test GET /health Lambda handler."""
    
    def test_health_endpoint_healthy(self, mock_event, mock_context, setup_aws_resources):
        """Test health endpoint returns 200 when all dependencies healthy."""
        from src.handlers.health import lambda_handler
        response = lambda_handler(mock_event, mock_context)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        
        body = json.loads(response['body'])
        assert body['status'] == "healthy"
        assert body['version'] == "1.0.0"
        assert 'timestamp' in body
        assert body['dependencies']['dynamodb'] == "healthy"
        assert body['dependencies']['s3'] == "healthy"
    
    def test_health_endpoint_degraded_s3(self, mock_event, mock_context, setup_aws_resources):
        """Test health endpoint returns 200 with degraded status when S3 fails."""
        from src.handlers.health import lambda_handler, check_dynamodb_health
        # Mock S3 to fail, but ensure DynamoDB is healthy
        with patch('src.handlers.health.check_s3_health', return_value=("unhealthy", 1000)):
            with patch('src.handlers.health.check_dynamodb_health', return_value=("healthy", 50)):
                response = lambda_handler(mock_event, mock_context)
                
                assert response['statusCode'] == 200  # Degraded returns 200
                body = json.loads(response['body'])
                assert body['status'] == "degraded"
                assert body['dependencies']['dynamodb'] == "healthy"
                assert body['dependencies']['s3'] == "unhealthy"
    
    def test_health_endpoint_unhealthy_dynamodb(self, mock_event, mock_context, setup_aws_resources):
        """Test health endpoint returns 503 when DynamoDB is unhealthy."""
        from src.handlers.health import lambda_handler
        # Mock DynamoDB to fail
        with patch('src.handlers.health.check_dynamodb_health', return_value=("unhealthy", 1000)):
            response = lambda_handler(mock_event, mock_context)
            
            assert response['statusCode'] == 503  # Unhealthy returns 503
            body = json.loads(response['body'])
            assert body['status'] == "unhealthy"
            assert body['dependencies']['dynamodb'] == "unhealthy"
    
    def test_health_endpoint_unexpected_error(self, mock_event, mock_context, setup_aws_resources):
        """Test health endpoint handles unexpected errors gracefully."""
        from src.handlers.health import lambda_handler
        # Mock health check to raise exception
        with patch('src.handlers.health.check_dynamodb_health', side_effect=Exception("Unexpected error")):
            response = lambda_handler(mock_event, mock_context)
            
            assert response['statusCode'] == 503
            body = json.loads(response['body'])
            assert body['status'] == "unhealthy"
    
    def test_health_endpoint_response_format(self, mock_event, mock_context, setup_aws_resources):
        """Test health endpoint response matches HealthResponse schema."""
        from src.handlers.health import lambda_handler
        response = lambda_handler(mock_event, mock_context)
        
        body = json.loads(response['body'])
        
        # Verify required fields
        assert 'status' in body
        assert 'timestamp' in body
        assert 'version' in body
        assert 'dependencies' in body
        
        # Verify status values
        assert body['status'] in ["healthy", "degraded", "unhealthy"]
        assert body['dependencies']['dynamodb'] in ["healthy", "degraded", "unhealthy"]
        assert body['dependencies']['s3'] in ["healthy", "degraded", "unhealthy"]
        
        # Verify timestamp format (ISO 8601)
        assert 'T' in body['timestamp']  # ISO 8601 contains 'T'
        assert 'Z' in body['timestamp'] or '+' in body['timestamp']  # Timezone indicator


class TestHealthCheckTimeouts:
    """Test health check timeout handling."""
    
    def test_dynamodb_check_timeout(self, setup_aws_resources):
        """Test DynamoDB check handles timeout gracefully."""
        from src.handlers.health import check_dynamodb_health
        # Mock describe_table to hang (simulate timeout)
        with patch('src.handlers.health.dynamodb_client.describe_table', side_effect=BotoCoreError()):
            status, latency = check_dynamodb_health()
            # Should return unhealthy on connection error
            assert status in ["unhealthy", "degraded"]
    
    def test_s3_check_timeout(self, setup_aws_resources):
        """Test S3 check handles timeout gracefully."""
        from src.handlers.health import check_s3_health
        # Mock head_bucket to hang (simulate timeout)
        with patch('src.handlers.health.s3_client.head_bucket', side_effect=BotoCoreError()):
            status, latency = check_s3_health()
            # Should return unhealthy on connection error
            assert status in ["unhealthy", "degraded"]


class TestHealthCheckErrorHandling:
    """Test health check error handling."""
    
    def test_dynamodb_client_error(self, setup_aws_resources):
        """Test DynamoDB check handles ClientError."""
        from src.handlers.health import check_dynamodb_health
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}}
        with patch('src.handlers.health.dynamodb_client.describe_table', side_effect=ClientError(error_response, 'DescribeTable')):
            status, latency = check_dynamodb_health()
            assert status == "unhealthy"
    
    def test_s3_client_error_404(self, setup_aws_resources):
        """Test S3 check handles 404 error."""
        from src.handlers.health import check_s3_health
        error_response = {'Error': {'Code': '404', 'Message': 'Not Found'}}
        with patch('src.handlers.health.s3_client.head_bucket', side_effect=ClientError(error_response, 'HeadBucket')):
            status, latency = check_s3_health()
            assert status == "unhealthy"
    
    def test_s3_client_error_transient(self, setup_aws_resources):
        """Test S3 check handles transient errors as degraded."""
        from src.handlers.health import check_s3_health
        error_response = {'Error': {'Code': 'SlowDown', 'Message': 'Slow down'}}
        with patch('src.handlers.health.s3_client.head_bucket', side_effect=ClientError(error_response, 'HeadBucket')):
            status, latency = check_s3_health()
            assert status == "degraded"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

