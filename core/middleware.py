from django.contrib.auth.models import User
from django.conf import settings

class DevAuthMiddleware:
    """
    Middleware that always sets a user in development environments.
    This ensures there's always an authenticated user available for development/testing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if settings.DEBUG and not request.user.is_authenticated:
            try:
                # Get or create a system user
                user, created = User.objects.get_or_create(
                    username='system',
                    defaults={
                        'email': 'system@replugit.com',
                        'first_name': 'System',
                        'last_name': 'User',
                        'is_active': True,
                    }
                )
                
                # Set the user on the request
                request.user = user
            except Exception as e:
                print(f"DevAuthMiddleware error: {e}")
        
        # Process the request normally
        response = self.get_response(request)
        return response
