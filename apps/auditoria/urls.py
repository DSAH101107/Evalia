# apps/auditoria/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.bitacora_view, name='bitacora'),
    path('evaluacion/<int:evaluacion_id>/', views.bitacora_evaluacion, name='bitacora_evaluacion'),
    path('api/resumen/', views.api_resumen, name='api_resumen'),
]
