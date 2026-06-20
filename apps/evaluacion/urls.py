from django.urls import path
from . import views
from .views_pdf import importar_pdf_aprendices, importar_pdf_aprendices_form, importar_pdf_checklists
from .views_importar_excel_checklists import importar_excel_checklists

from rest_framework.routers import DefaultRouter
from .api_views import (
    AprendizViewSet, EvaluacionViewSet, ResultadoViewSet, InvitacionViewSet, api_estadisticas,
)

router = DefaultRouter()
router.register(r'api/aprendices',  AprendizViewSet,  basename='api-aprendiz')
router.register(r'api/evaluaciones', EvaluacionViewSet, basename='api-evaluacion')
router.register(r'api/resultados',   ResultadoViewSet, basename='api-resultado')
router.register(r'api/invitaciones', InvitacionViewSet, basename='api-invitacion')

urlpatterns = [
    path('', views.home, name='home'),

    # ── Evaluación GAES (batch por GAES) ──────────────────────────
    path('gaes/<int:gaes_id>/iniciar/', views.evaluar_gaes, name='evaluar_gaes'),
    path('gaes/<int:gaes_id>/pdf/<int:checklist_id>/', views.generar_pdf_gaes_evaluacion, name='generar_pdf_gaes_evaluacion'),
    path('api/checklist/<int:checklist_id>/items/', views.api_checklist_items, name='api_checklist_items'),

    # ── Aprendices ─────────────────────────────────────────
    path('aprendices/', views.lista_aprendices, name='lista_aprendices'),
    path('aprendices/crear/', views.crear_aprendiz, name='crear_aprendiz'),
    path('aprendices/<int:aprendiz_id>/editar/', views.editar_aprendiz, name='editar_aprendiz'),
    path('aprendices/importar/', views.importar_excel, name='importar_excel'),
    path('aprendices/importar/asignar-gaes/', views.importar_excel_asignar_gaes, name='importar_excel_asignar_gaes'),
    path('aprendices/importar-csv/', views.importar_csv_aprendices, name='importar_csv_aprendices'),
    path('aprendices/importar-pdf/', importar_pdf_aprendices, name='importar_pdf_aprendices'),
    path('bloquear-aprendiz/<int:aprendiz_id>/', views.bloquear_aprendiz, name='bloquear_aprendiz'),
    path('aprendices/eliminar/<int:aprendiz_id>/', views.eliminar_aprendiz_post, name='eliminar_aprendiz'),

    # ── Checklists / Evaluaciones ──────────────────────────
    path('checklists/', views.lista_checklists, name='lista_checklists'),
    path('checklists/', views.lista_checklists, name='lista_checklists_evaluacion'),
    path('checklists/crear/', views.crear_checklist, name='crear_checklist'),
    path('checklists/importar-pdf/', importar_pdf_checklists, name='importar_pdf_checklists'),
    path('checklists/importar-excel/', importar_excel_checklists, name='importar_excel_checklists'),
    path('checklists/importar-excel/', importar_excel_checklists, name='importar_excel_checklists_evaluacion'),
    path('checklists/eliminar/<int:checklist_id>/', views.eliminar_checklist, name='eliminar_checklist'),
    path('checklists/<int:checklist_id>/', views.ver_editar_checklist, name='ver_editar_checklist'),
    path('checklists/<int:checklist_id>/imprimir/', views.imprimir_checklist, name='imprimir_checklist'),
    path('checklists/<int:checklist_id>/limpio/', views.ver_checklist_limpio, name='ver_checklist_limpio'),

    # ── Evaluación ─────────────────────────────────────────
    path('evaluacion/iniciar/<int:aprendiz_id>/', views.iniciar_evaluacion, name='iniciar_evaluacion'),
    path('evaluacion/evaluar/<int:evaluacion_id>/', views.evaluar_aprendiz, name='evaluar_aprendiz'),
    path('evaluaciones/', views.lista_evaluaciones, name='lista_evaluaciones'),
    path('evaluaciones/eliminar/<int:evaluacion_id>/', views.eliminar_evaluacion, name='eliminar_evaluacion'),
    path('fichas/<int:ficha_id>/evaluacion/', views.detalle_ficha_evaluacion, name='detalle_ficha_evaluacion'),
    path('fichas/<int:ficha_id>/reporte/', views.generar_reporte_ficha, name='generar_reporte_ficha'),

# ── Resultados ─────────────────────────────────────────
path('resultados/', views.lista_resultados, name='lista_resultados'),
path('resultados/<int:resultado_id>/', views.ver_resultado, name='ver_resultado'),
path('resultados/<int:resultado_id>/pdf/', views.generar_reporte_pdf, name='generar_reporte_pdf'),
path('resultados/exportar-excel/', views.exportar_resultados_excel, name='exportar_resultados_excel'),
path('resultados/eliminar/<int:resultado_id>/', views.eliminar_resultado, name='eliminar_resultado'),

    # ── Invitaciones ───────────────────────────────────────
    path('admin/invitaciones/', views.enviar_invitacion, name='enviar_invitacion'),
    path('invitaciones/jurado/', views.invitaciones_jurado, name='invitaciones_jurado'),
    path('invitacion/<int:invitacion_id>/aceptar/', views.aceptar_invitacion, name='aceptar_invitacion'),
    path('invitacion/<int:invitacion_id>/rechazar/', views.rechazar_invitacion, name='rechazar_invitacion'),

    # ── API JSON local ─────────────────────────────────────
    path('api/consumir-estadisticas/', views.consumir_api_estadisticas, name='consumir_api_estadisticas'),
    path('api/estadisticas-basicas/', views.api_estadisticas_basicas, name='api_estadisticas_basicas'),
    path('api/chart/gaes/', views.api_chart_gaes, name='api_chart_gaes'),
    path('api/estadisticas/', api_estadisticas, name='api_estadisticas'),
]

urlpatterns += router.urls
