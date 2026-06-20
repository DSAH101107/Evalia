# apps/gaes/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_fichas_gaes, name='lista_fichas_gaes'),
    path('gaes/', views.lista_gaes, name='lista_gaes'),
    path('gaes/instructor/', views.lista_gaes_instructor, name='lista_gaes_instructor'),
    path('ficha/<int:pk>/', views.detalle_ficha_gaes, name='detalle_ficha_gaes'),
    path('crear/', views.crear_gaes, name='crear_gaes'),
    path('<int:pk>/', views.detalle_gaes, name='detalle_gaes'),
    path('<int:pk>/editar/', views.editar_gaes, name='editar_gaes'),
    path('<int:pk>/eliminar/', views.eliminar_gaes, name='eliminar_gaes'),
    path('<int:pk>/agregar-aprendices/', views.agregar_aprendices_gaes, name='agregar_aprendices_gaes'),
    path('<int:pk>/aprendiz/<int:aprendiz_id>/eliminar/', views.eliminar_aprendiz_gaes, name='eliminar_aprendiz_gaes'),
    path('<int:pk>/aprendiz/<int:aprendiz_id>/transferir/', views.transferir_aprendiz_gaes, name='transferir_aprendiz_gaes'),
]
