# apps/fichas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_fichas, name='lista_fichas'),
    path('crear/', views.crear_ficha, name='crear_ficha'),
    path('<int:pk>/', views.detalle_ficha, name='detalle_ficha'),
    path('<int:pk>/editar/', views.editar_ficha, name='editar_ficha'),
    path('<int:pk>/eliminar/', views.eliminar_ficha, name='eliminar_ficha'),
    path('<int:pk>/actualizar-gaes/', views.actualizar_gaes_ficha, name='actualizar_gaes_ficha'),
    path('<int:pk>/api/gaes/', views.api_gaes_por_ficha, name='api_gaes_por_ficha'),
    path('gaes/<int:pk>/integrantes/', views.api_integrantes_gaes, name='api_integrantes_gaes'),
    path('lista-con-aprendices/', views.lista_fichas_con_aprendices, name='lista_fichas_con_aprendices'),
    path('<int:ficha_id>/aprendices/', views.aprendices_por_ficha, name='aprendices_por_ficha'),
    path('<int:ficha_id>/ver-gaes/', views.ver_gaes_ficha, name='ver_gaes_ficha'),
    path('gaes-con-aprendices/', views.lista_gaes_con_aprendices, name='lista_gaes_con_aprendices'),
]
