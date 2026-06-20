from django.contrib import admin
from .models import LogAuditoria, BitacoraEvaluacion


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'usuario', 'modulo', 'accion', 'descripcion')
    list_filter  = ('modulo', 'accion', 'usuario')
    search_fields = ('usuario__username', 'descripcion', 'modulo')
    readonly_fields = ('modulo', 'accion', 'descripcion', 'objeto_id', 'objeto_tipo',
                       'ip_address', 'user_agent', 'usuario', 'created_at')
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(BitacoraEvaluacion)
class BitacoraEvaluacionAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'version', 'estado_anterior', 'estado_nuevo',
                    'modificado_por', 'created_at')
    list_filter  = ('estado_nuevo', 'modificado_por')
    search_fields = ('evaluacion__id',)
    ordering = ['-created_at']
    readonly_fields = ('evaluacion', 'version', 'estado_anterior', 'estado_nuevo',
                       'modificado_por', 'created_at')
