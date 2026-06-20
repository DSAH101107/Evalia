# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="EVALIA API",
      default_version='v1',
      description=(
          "API REST del Sistema de Evaluacion de Aprendices SENA - EVALIA. "
          "Incluye endpoints para usuarios, aprendices, fichas, competencias, "
          "evaluaciones, resultados, GAES, invitaciones y auditoria."
      ),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/usuarios/login/?welcome=1', permanent=False), name='home'),

    # Módulo de Autenticación y Usuarios
    path('usuarios/', include('apps.usuarios.urls')),

    # Módulo de Trimestres
    path('trimestres/', include('apps.trimestres.urls')),

    # Módulo de GAES
    path('gaes/', include('apps.gaes.urls')),

    # Módulo de Jurados
    path('jurados/', include('apps.jurados.urls')),

    # Módulo de Fichas
    path('fichas/', include('apps.fichas.urls')),

    # Módulo de Competencias (checklists, fases, importacion)
    path('competencias/', include('apps.competencias.urls')),

    # Módulo de Evaluación (evaluaciones, resultados, invitaciones)
    path('evaluacion/', include('apps.evaluacion.urls')),

    # Módulo de Aprendices
    path('aprendices/', include('apps.aprendices.urls')),

    # Módulo de Reportes
    path('reportes/', include('apps.reportes.urls')),

    # Módulo de Notificaciones
    path('notificaciones/', include('apps.notificaciones.urls')),

    # Módulo de Auditoría
    path('auditoria/', include('apps.auditoria.urls')),

    # ── Swagger / Documentación API ───────────────────────
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
