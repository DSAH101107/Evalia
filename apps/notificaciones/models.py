from django.db import models
from apps.usuarios.models import Usuario


class Notificacion(models.Model):
    """Notificación generada automáticamente al aceptar/rechazar invitación o crear evaluación."""

    TIPO_ACEPTACION = 'aceptacion'
    TIPO_RECHAZO = 'rechazo'
    TIPO_EVALUACION = 'evaluacion'
    TIPO_RESULTADO = 'resultado'
    TIPO_SISTEMA = 'sistema'
    TIPO_OTRO = 'otro'

    TIPO_CHOICES = [
        (TIPO_ACEPTACION, 'Aceptación de invitación'),
        (TIPO_RECHAZO, 'Rechazo de invitación'),
        (TIPO_EVALUACION, 'Evaluación creada/completada'),
        (TIPO_RESULTADO, 'Resultado publicado'),
        (TIPO_SISTEMA, 'Sistema'),
        (TIPO_OTRO, 'Otro'),
    ]

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_LEIDA = 'leida'
    ESTADO_ARCHIVADA = 'archivada'

    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_LEIDA, 'Leída'),
        (ESTADO_ARCHIVADA, 'Archivada'),
    ]

    destinatario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='notificaciones',
    )
    emisor = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificaciones_enviadas',
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_SISTEMA)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    url_relacionada = models.CharField(max_length=255, blank=True, default='')
    fecha_envio = models.DateTimeField(auto_now_add=True)
    fecha_leida = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_envio']
        indexes = [
            models.Index(fields=['destinatario', 'estado']),
            models.Index(fields=['fecha_envio']),
        ]

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo} → {self.destinatario}'
