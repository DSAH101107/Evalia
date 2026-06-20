# apps/reportes/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='reportes_home'),
    path('estado/<str:estado>/', views.aprendices_estado, name='reportes_aprendices_estado'),
    path('ficha/<int:ficha_id>/', views.resultados_por_ficha, name='reportes_ficha'),
    path('trimestre/<int:trimestre_id>/', views.resultados_por_trimestre, name='reportes_trimestre'),
    path('competencia/<int:competencia_id>/', views.resultados_por_competencia, name='reportes_competencia'),
    path('historial/', views.historial_evaluaciones, name='reportes_historial'),
    path('pdf/<str:tipo>/', views.exportar_pdf, name='reportes_pdf'),
    path('excel/<str:tipo>/', views.exportar_excel, name='reportes_excel'),
]
