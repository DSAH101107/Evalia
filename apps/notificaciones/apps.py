# apps/notificaciones/apps.py
from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notificaciones'

    def ready(self):
        # Import signals to register them
        import apps.notificaciones.signals  # noqa: F401
