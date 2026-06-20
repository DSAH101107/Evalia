from django.db import models
from apps.usuarios.models import Usuario


class LogAuditoria(models.Model):
    """Bitácora de toda acción realizada en el sistema."""

    ACCION_CRIAR       = 'crear'
    ACCION_EDITAR      = 'editar'
    ACCION_ELIMINAR    = 'eliminar'
    ACCION_IMPORTAR    = 'importar'
    ACCION_EXPORTAR    = 'exportar'
    ACCION_APROBAR     = 'aprobar'
    ACCION_RECHAZAR    = 'rechazar'
    ACCION_BLOQUEAR    = 'bloquear'
    ACCION_DESBLOQUEAR = 'desbloquear'
    ACCION_INICIAR_EVAL = 'iniciar_eval'
    ACCION_FINALIZAR_EVAL = 'finalizar_eval'
    ACCION_REEVALUAR  = 'reevaluar'

    ACCIONES = [
        (ACCION_CRIAR,       'Crear'),
        (ACCION_EDITAR,      'Editar'),
        (ACCION_ELIMINAR,    'Eliminar'),
        (ACCION_IMPORTAR,    'Importar'),
        (ACCION_EXPORTAR,    'Exportar'),
        (ACCION_APROBAR,     'Aprobar'),
        (ACCION_RECHAZAR,    'Rechazar'),
        (ACCION_BLOQUEAR,    'Bloquear'),
        (ACCION_DESBLOQUEAR, 'Desbloquear'),
        (ACCION_INICIAR_EVAL,   'Iniciar Evaluación'),
        (ACCION_FINALIZAR_EVAL, 'Finalizar Evaluación'),
        (ACCION_REEVALUAR,      'Re-Evaluación'),
    ]

    MODULO_USUARIOS       = 'usuarios'
    MODULO_APRENDICES     = 'aprendices'
    MODULO_EVALUACION     = 'evaluacion'
    MODULO_CHECKLISTS     = 'checklists'
    MODULO_RESULTADOS     = 'resultados'
    MODULO_INVITACIONES   = 'invitaciones'
    MODULO_NOTIFICACIONES = 'notificaciones'
    MODULO_REPORTES       = 'reportes'
    MODULO_FICHAS         = 'fichas'
    MODULO_COMPETENCIAS   = 'competencias'
    MODULO_GAES           = 'gaes'
    MODULO_TRIMESTRES     = 'trimestres'

    MODULOS = [
        (MODULO_USUARIOS,       'Usuarios'),
        (MODULO_APRENDICES,     'Aprendices'),
        (MODULO_EVALUACION,     'Evaluación'),
        (MODULO_CHECKLISTS,     'Checklists'),
        (MODULO_RESULTADOS,     'Resultados'),
        (MODULO_INVITACIONES,   'Invitaciones'),
        (MODULO_NOTIFICACIONES, 'Notificaciones'),
        (MODULO_REPORTES,       'Reportes'),
        (MODULO_FICHAS,         'Fichas'),
        (MODULO_COMPETENCIAS,   'Competencias'),
        (MODULO_GAES,           'GAES'),
        (MODULO_TRIMESTRES,     'Trimestres'),
    ]

    modulo      = models.CharField(max_length=30, choices=MODULOS)
    accion      = models.CharField(max_length=30, choices=ACCIONES)
    descripcion = models.TextField(blank=True)
    objeto_id   = models.CharField(max_length=30, blank=True)
    objeto_tipo = models.CharField(max_length=60, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True)

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_auditoria'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['modulo', 'created_at']),
            models.Index(fields=['usuario', 'created_at']),
            models.Index(fields=['accion', 'created_at']),
        ]
        verbose_name = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"

    def __str__(self):
        usuario_str = getattr(self.usuario, 'username', '—')
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {usuario_str} — {self.get_accion_display()} — {self.modulo}"


class BitacoraEvaluacion(models.Model):
    """Historial de cambios específicos por evaluación."""

    evaluacion = models.ForeignKey(
        'evaluacion.Evaluacion',
        on_delete=models.CASCADE,
        related_name='bitacora'
    )
    version = models.PositiveIntegerField(default=1)
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo   = models.CharField(max_length=30, blank=True)
    observaciones  = models.TextField(blank=True)
    modificado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cambios_evaluacion'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('evaluacion', 'version')
        verbose_name = "Bitácora de Evaluación"
        verbose_name_plural = "Bitácoras de Evaluación"

    def __str__(self):
        return f"Evaluación {self.evaluacion_id} — v{self.version} — {self.created_at.strftime('%Y-%m-%d %H:%M')}"
