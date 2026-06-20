from django.urls import path
from . import views
from . import views_instructor_tables


urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('admin/ficha-resultados/', views.admin_ficha_resultados, name='admin_ficha_resultados'),
    path('admin/ficha/<int:ficha_id>/gaes/', views.admin_ficha_gaes, name='admin_ficha_gaes'),
    path('admin/gaes/<int:gaes_id>/aprendices/', views.admin_gaes_aprendices, name='admin_gaes_aprendices'),
    path('dashboard/instructor/', views.dashboard_instructor, name='dashboard_instructor'),
    path('dashboard/jurado/', views.dashboard_jurado, name='usuario_dashboard_jurado'),
    path('dashboard/aprendiz/', views.dashboard_aprendiz, name='dashboard_aprendiz'),
    path('dashboard/instructor/tablas/', views_instructor_tables.instructor_tablas, name='dashboard_instructor_tablas'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/grupos/', views.lista_usuarios_por_grupos, name='lista_usuarios_por_grupos'),
    
    path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:usuario_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('instructores/', views.lista_instructores, name='lista_instructores'),
    path('instructores/<int:instructor_id>/invitacion/', views.enviar_invitacion_email, name='enviar_invitacion_email'),
    path('fichas/<int:ficha_id>/invitacion/', views.enviar_invitacion_ficha, name='enviar_invitacion_ficha'),
    path('invitaciones/<int:invitacion_id>/', views.ver_invitacion_ficha, name='ver_invitacion_ficha'),
    path('invitaciones/<int:invitacion_id>/compartir/', views.compartir_invitacion, name='compartir_invitacion'),
]
