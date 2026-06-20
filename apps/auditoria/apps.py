# apps/auditoria/apps.py
from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auditoria'
    verbose_name = "Auditoría"

    def ready(self):
        # Import signals to register them
        import apps.auditoria.signals  # noqa: F401
