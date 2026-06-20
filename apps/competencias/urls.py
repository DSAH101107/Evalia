# apps/competencias/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_competencias, name='lista_competencias'),
    path('crear/', views.crear_competencia, name='crear_competencia'),
    path('<int:pk>/', views.detalle_competencia, name='detalle_competencia'),
    path('<int:pk>/editar/', views.editar_competencia, name='editar_competencia'),
    path('<int:pk>/eliminar/', views.eliminar_competencia, name='eliminar_competencia'),
    path('fases/', views.lista_fases, name='lista_fases'),
    path('fases/crear/', views.crear_fase, name='crear_fase'),
    path('fases/<int:pk>/editar/', views.editar_fase, name='editar_fase'),
    path('fases/<int:pk>/eliminar/', views.eliminar_fase, name='eliminar_fase'),
    path('checklists/', views.lista_checklists, name='lista_checklists'),
    path('checklists/crear/', views.crear_checklist, name='crear_checklist'),
    path('checklists/<int:pk>/', views.ver_checklist, name='ver_checklist'),
    path('checklists/<int:pk>/editar/', views.editar_checklist, name='editar_checklist'),
    path('checklists/<int:pk>/eliminar/', views.eliminar_checklist, name='eliminar_checklist'),
    path('importar-excel/', views.importar_excel_checklists, name='importar_excel_checklists'),
    path('api/competencias-por-fase-ficha/', views.api_competencias_por_fase_ficha,
         name='api_competencias_por_fase_ficha'),
]
