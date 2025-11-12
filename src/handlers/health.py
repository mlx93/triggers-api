"""
GET /health Lambda handler for health check endpoint.

Checks DynamoDB and S3 connectivity and returns system health status.
Returns 200 for healthy/degraded, 503 for unhealthy per OPEN_QUESTIONS.md Q7.
"""
import os
import json
import time
from typing import Dict, Any, Literal
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from src.models.schemas import HealthResponse, HealthDependencies
from src.lib.logging import get_logger

logger = get_logger(__name__)

# Get environment variables
EVENTS_TABLE_NAME = os.environ.get('EVENTS_TABLE', 'zapier-triggers-events-dev')
EVENTS_BUCKET_NAME = os.environ.get('EVENTS_BUCKET', 'zapier-triggers-events-dev')
API_VERSION = os.environ.get('API_VERSION', '1.0.0')

# Initialize AWS clients
dynamodb_client = boto3.client('dynamodb')
s3_client = boto3.client('s3')

# Health check timeouts (milliseconds)
DYNAMODB_TIMEOUT_MS = 100  # Healthy threshold: <100ms
S3_TIMEOUT_MS = 100  # Healthy threshold: <100ms
MAX_CHECK_TIMEOUT_MS = 5000  # Maximum time to wait for dependency check (5 seconds)


def check_dynamodb_health() -> tuple[Literal["healthy", "degraded", "unhealthy"], float]:
    """
    Check DynamoDB connectivity.
    
    Uses describe_table() to check if table exists and is accessible.
    Returns status and latency in milliseconds.
    
    Returns:
        Tuple of (status, latency_ms)
        - healthy: Response within 100ms
        - degraded: Response between 100ms and 500ms
        - unhealthy: No response or error
    """
    start_time = time.time()
    
    try:
        dynamodb_client.describe_table(TableName=EVENTS_TABLE_NAME)
        latency_ms = (time.time() - start_time) * 1000
        
        if latency_ms < DYNAMODB_TIMEOUT_MS:
            return "healthy", latency_ms
        elif latency_ms < MAX_CHECK_TIMEOUT_MS:
            return "degraded", latency_ms
        else:
            return "unhealthy", latency_ms
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        latency_ms = (time.time() - start_time) * 1000
        
        # ResourceNotFoundException means table doesn't exist (unhealthy)
        # Other errors might be transient (degraded)
        if error_code == 'ResourceNotFoundException':
            logger.error(f"DynamoDB table not found: {EVENTS_TABLE_NAME}")
            return "unhealthy", latency_ms
        else:
            logger.warning(f"DynamoDB error: {error_code}")
            return "degraded", latency_ms
            
    except BotoCoreError as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"DynamoDB connection error: {e}")
        return "unhealthy", latency_ms
        
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Unexpected DynamoDB error: {e}")
        return "unhealthy", latency_ms


def check_s3_health() -> tuple[Literal["healthy", "degraded", "unhealthy"], float]:
    """
    Check S3 connectivity.
    
    Uses head_bucket() to check if bucket exists and is accessible.
    Returns status and latency in milliseconds.
    
    Returns:
        Tuple of (status, latency_ms)
        - healthy: Response within 100ms
        - degraded: Response between 100ms and 500ms
        - unhealthy: No response or error
    """
    start_time = time.time()
    
    try:
        s3_client.head_bucket(Bucket=EVENTS_BUCKET_NAME)
        latency_ms = (time.time() - start_time) * 1000
        
        if latency_ms < S3_TIMEOUT_MS:
            return "healthy", latency_ms
        elif latency_ms < MAX_CHECK_TIMEOUT_MS:
            return "degraded", latency_ms
        else:
            return "unhealthy", latency_ms
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        latency_ms = (time.time() - start_time) * 1000
        
        # 404 means bucket doesn't exist (unhealthy)
        # 403 might mean permissions issue (unhealthy)
        # Other errors might be transient (degraded)
        if error_code in ['404', '403', 'NoSuchBucket']:
            logger.error(f"S3 bucket not found or inaccessible: {EVENTS_BUCKET_NAME}")
            return "unhealthy", latency_ms
        else:
            logger.warning(f"S3 error: {error_code}")
            return "degraded", latency_ms
            
    except BotoCoreError as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"S3 connection error: {e}")
        return "unhealthy", latency_ms
        
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Unexpected S3 error: {e}")
        return "unhealthy", latency_ms


def determine_overall_status(
    dynamodb_status: str,
    s3_status: str
) -> Literal["healthy", "degraded", "unhealthy"]:
    """
    Determine overall system status based on dependency statuses.
    
    Logic per OPEN_QUESTIONS.md Q7:
    - Healthy: All dependencies healthy
    - Degraded: One dependency failing/slow, but DynamoDB works (core dependency)
    - Unhealthy: DynamoDB unavailable (core dependency)
    
    Args:
        dynamodb_status: DynamoDB status
        s3_status: S3 status
        
    Returns:
        Overall system status
    """
    # Unhealthy: DynamoDB is down (core dependency)
    if dynamodb_status == "unhealthy":
        return "unhealthy"
    
    # Degraded: DynamoDB works but S3 is down/slow
    if s3_status in ["degraded", "unhealthy"]:
        return "degraded"
    
    # Healthy: Both dependencies healthy
    if dynamodb_status == "healthy" and s3_status == "healthy":
        return "healthy"
    
    # Degraded: DynamoDB is slow but works
    if dynamodb_status == "degraded":
        return "degraded"
    
    # Default to degraded if unclear
    return "degraded"


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /health Lambda handler.
    
    Checks DynamoDB and S3 connectivity and returns health status.
    Returns 200 for healthy/degraded, 503 for unhealthy per OPEN_QUESTIONS.md Q7.
    
    Args:
        event: Lambda event dictionary
        context: Lambda context
        
    Returns:
        Lambda response dictionary with statusCode, body, headers
    """
    try:
        # Check dependencies
        dynamodb_status, dynamodb_latency = check_dynamodb_health()
        s3_status, s3_latency = check_s3_health()
        
        # Determine overall status
        overall_status = determine_overall_status(dynamodb_status, s3_status)
        
        # Build dependencies status
        dependencies = HealthDependencies(
            dynamodb=dynamodb_status,
            s3=s3_status
        )
        
        # Build health response
        health_response = HealthResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=API_VERSION,
            dependencies=dependencies
        )
        
        # Log health check result
        logger.info(
            f"Health check: {overall_status}",
            extra={
                "dynamodb_status": dynamodb_status,
                "dynamodb_latency_ms": dynamodb_latency,
                "s3_status": s3_status,
                "s3_latency_ms": s3_latency
            }
        )
        
        # Return 200 for healthy/degraded, 503 for unhealthy
        status_code = 200 if overall_status in ["healthy", "degraded"] else 503
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': health_response.model_dump_json()
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in health handler: {e}", exc_info=True)
        
        # Return unhealthy status on unexpected errors
        health_response = HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=API_VERSION,
            dependencies=HealthDependencies(
                dynamodb="unhealthy",
                s3="unhealthy"
            )
        )
        
        return {
            'statusCode': 503,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': health_response.model_dump_json()
        }
