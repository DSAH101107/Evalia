# apps/competencias/apps.py
from django.apps import AppConfig


class CompetenciasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.competencias'
    verbose_name = "Competencias"

    def ready(self):
        import apps.competencias.signals  # noqa
