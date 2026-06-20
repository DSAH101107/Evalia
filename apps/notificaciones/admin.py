from django.contrib import admin
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'destinatario', 'tipo', 'estado', 'fecha_envio', 'fecha_leida')
    search_fields = ('titulo', 'mensaje', 'destinatario__username', 'destinatario__email')
    list_filter = ('tipo', 'estado', 'fecha_envio')
    ordering = ('-fecha_envio',)
    list_select_related = ('destinatario', 'emisor')
