import json
import logging
import time
from uuid import uuid4

logger = logging.getLogger('api.requests')

class ApiRequestLoggingMiddleware:
    """
    Middleware to log detailed information about API requests and responses.
    This helps with debugging API issues during product family operations.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only process API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        # Generate a unique request ID for tracking
        request_id = str(uuid4())[:8]
        
        # Log request details
        self._log_request(request, request_id)
        
        # Process the request and time it
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        # Log response details
        self._log_response(response, request_id, duration)
        
        return response
    
    def _log_request(self, request, request_id):
        """Log details about the incoming request"""
        method = request.method
        path = request.path
        query_params = dict(request.GET)
        
        # Try to get request body for POST/PUT/PATCH requests
        body = None
        if method in ('POST', 'PUT', 'PATCH'):
            if hasattr(request, 'body'):
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    # Redact sensitive information if needed
                    if body and isinstance(body, dict):
                        if 'password' in body:
                            body['password'] = '********'
                except Exception:
                    body = '<Unable to parse request body>'
          # Safely check if user is available (will be after AuthenticationMiddleware)
        has_user = hasattr(request, 'user')
        
        log_data = {
            'request_id': request_id,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'method': method,
            'path': path,
            'query_params': query_params,
            'body': body,
            'user_id': getattr(request.user, 'id', None) if has_user else None,
            'is_authenticated': request.user.is_authenticated if has_user else False
        }
        
        logger.info(f"API Request [{request_id}]: {method} {path}")
        logger.debug(f"API Request Details [{request_id}]: {json.dumps(log_data, default=str)}")
    
    def _log_response(self, response, request_id, duration):
        """Log details about the outgoing response"""
        status_code = response.status_code
        
        # Try to get response body for JSON responses
        body = None
        if hasattr(response, 'content') and response.get('Content-Type', '') == 'application/json':
            try:
                body = json.loads(response.content.decode('utf-8'))
                # Redact sensitive information if needed
                if 'token' in body:
                    body['token'] = '********'
            except Exception:
                body = '<Unable to parse response body>'
        
        log_data = {
            'request_id': request_id,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'status_code': status_code,
            'duration_ms': int(duration * 1000),
            'body': body
        }
        
        # Log with appropriate level based on status code
        if 200 <= status_code < 300:
            logger.info(f"API Response [{request_id}]: {status_code} ({int(duration * 1000)}ms)")
            logger.debug(f"API Response Details [{request_id}]: {json.dumps(log_data, default=str)}")
        elif 400 <= status_code < 500:
            logger.warning(f"API Client Error [{request_id}]: {status_code} ({int(duration * 1000)}ms)")
            logger.warning(f"API Response Details [{request_id}]: {json.dumps(log_data, default=str)}")
        elif 500 <= status_code < 600:
            logger.error(f"API Server Error [{request_id}]: {status_code} ({int(duration * 1000)}ms)")
            logger.error(f"API Response Details [{request_id}]: {json.dumps(log_data, default=str)}")
        else:
            logger.info(f"API Response [{request_id}]: {status_code} ({int(duration * 1000)}ms)")
