from django.core.checks import register, Error
from django.conf import settings

@register()
def check_walmart_settings(app_configs, **kwargs):
    errors = []
    
    if not settings.WALMART_CA_CLIENT_SECRET:
        errors.append(
            Error(
                'WALMART_CA_CLIENT_SECRET not set',
                hint='Set WALMART_CA_CLIENT_SECRET in .env file',
                obj='settings'
            )
        )
    
    return errors