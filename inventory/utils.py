from rest_framework.response import Response
from rest_framework import status

def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    """Generate consistent success response format"""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return Response(response, status=status_code)

def error_response(message, status_code=status.HTTP_400_BAD_REQUEST, errors=None):
    """Generate consistent error response format"""
    response = {'success': False, 'error': message}
    if errors:
        response['errors'] = errors
    return Response(response, status=status_code)