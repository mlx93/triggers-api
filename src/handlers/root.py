"""
GET / Lambda handler for API root endpoint.

Returns API information, version, and available endpoints.
"""
import json
from typing import Dict, Any
from datetime import datetime, timezone

from src.lib.logging import get_logger

logger = get_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET / requests.
    
    Returns API information including:
    - API name and version
    - Available endpoints
    - Documentation links
    - Authentication requirements
    """
    api_info = {
        "name": "Triggers API",
        "version": "1.0.0",
        "description": "Real-time event ingestion and delivery API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "POST /events": "Ingest a new event",
            "GET /inbox": "Retrieve events from inbox",
            "POST /inbox/ack": "Acknowledge events",
            "GET /health": "Check API health status"
        },
        "authentication": {
            "type": "API Key",
            "header": "X-API-Key",
            "format": "ak_{32chars}"
        },
        "documentation": {
            "swagger_ui": "http://triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com",
            "openapi_spec": "http://triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com/openapi.yaml"
        },
        "links": {
            "health": "/health",
            "events": "/events",
            "inbox": "/inbox"
        }
    }
    
    logger.info("Root endpoint accessed")
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(api_info, indent=2)
    }

