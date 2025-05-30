from django.apps import AppConfig


class WarrantiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'warranties'
    
    def ready(self):
        """Import signals when the app is ready."""
        import warranties.signals
