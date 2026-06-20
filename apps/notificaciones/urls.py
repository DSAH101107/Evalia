from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_notificaciones, name='lista_notificaciones'),
    path('marcar-leida/<int:notificacion_id>/', views.marcar_leida, name='marcar_leida'),
    path('api/', views.notificaciones_api, name='notificaciones_api'),
]
