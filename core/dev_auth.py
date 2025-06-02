from django.contrib.auth.models import User
from django.conf import settings

class DevAuthenticationBackend:
    """
    Authentication backend that always returns a specific user in development.
    This simplifies testing by bypassing authentication in development environments.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Always authenticate as the development user when in DEBUG mode
        """
        if not settings.DEBUG:
            return None
            
        try:
            # Get or create a dev user
            user, created = User.objects.get_or_create(
                username='devuser',
                defaults={
                    'email': 'dev@example.com',
                    'first_name': 'Development',
                    'last_name': 'User',
                    'is_staff': True,
                    'is_active': True,
                    'is_superuser': True
                }
            )
            
            if created:
                # Set a simple password for the dev user if newly created
                user.set_password('devpassword')
                user.save()
                
            return user
        except Exception as e:
            print(f"DevAuthenticationBackend error: {e}")
            return None
    
    def get_user(self, user_id):
        """
        Retrieve user by ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
