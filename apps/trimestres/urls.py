# apps/trimestres/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_trimestres, name='lista_trimestres'),
    path('crear/', views.crear_trimestre, name='crear_trimestre'),
    path('<int:pk>/', views.detalle_trimestre, name='detalle_trimestre'),
    path('<int:pk>/editar/', views.editar_trimestre, name='editar_trimestre'),
    path('<int:pk>/eliminar/', views.eliminar_trimestre, name='eliminar_trimestre'),
]
