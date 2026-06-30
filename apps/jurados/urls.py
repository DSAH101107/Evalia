# apps/jurados/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard_jurado'),
    path('gaes/', views.jurado_gaes, name='jurado_gaes'),
    path('mi-ficha/', views.mi_ficha, name='jurado_mi_ficha'),
    path('mi-checklist/', views.mi_checklist, name='jurado_mi_checklist'),
    path('mi-checklist/<int:checklist_id>/', views.mi_checklist, name='jurado_mi_checklist_id'),
    path('mis-resultados/', views.mis_resultados, name='jurado_mis_resultados'),
    path('mis-evaluaciones/', views.mis_evaluaciones, name='jurado_mis_evaluaciones'),
    path('evaluar-gaes/<int:gaes_id>/', views.evaluar_gaes, name='evaluar_gaes'),
    path('evaluaciones-gaes/<int:gaes_id>/', views.jurado_evaluaciones_gaes, name='jurado_evaluaciones_gaes'),
    path('imprimir/<int:evaluacion_id>/', views.imprimir_reporte, name='jurado_imprimir_reporte'),
]
