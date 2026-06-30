# apps/notificaciones/signals.py
"""
Signals para creacion automatica de notificaciones.

Se dispachan:
  - post_save Invitacion: crea notificacion cuando se acepta/rechaza
  - post_save Evaluacion (estado=completada): crea notificacion de resultado
  - post_save Resultado: crea notificacion cuando se publica resultado
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Notificacion

Usuario = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _crear_notificacion(
    destinatario,
    tipo,
    titulo,
    mensaje,
    emisor=None,
    url_relacionada='',
):
    """Crea una Notificacion de forma segura (sin excepciones)."""
    try:
        if destinatario is None:
            return None
        Notificacion.objects.create(
            destinatario=destinatario,
            emisor=emisor,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            url_relacionada=url_relacionada,
        )
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("No se pudo crear notificacion: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Signal: Invitacion aceptada / rechazada
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Invitacion')
def invitacion_cambiada(sender, instance, created, **kwargs):
    from apps.evaluacion.models import Invitacion

    if created:
        # Nueva invitacion: notificar al invitado (si ya esta asignado)
        if instance.instructor_invitado:
            _crear_notificacion(
                destinatario=instance.instructor_invitado,
                tipo=Notificacion.TIPO_ACEPTACION,
                titulo='Nueva invitacion para ser jurado',
                mensaje=(
                    f'El administrador {instance.instructor.username} te ha invitado '
                    f'a participar como jurado. Fecha: {instance.fecha_evaluacion or "Por definir"}.'
                ),
                emisor=instance.instructor,
                url_relacionada=f'/evaluacion/',
            )
        return

    # Invitacion existente que cambio de estado
    if instance.estado == Invitacion.ESTADO_ACEPTADA and instance.instructor_invitado:
        _crear_notificacion(
            destinatario=instance.instructor,
            tipo=Notificacion.TIPO_ACEPTACION,
            titulo='Invitacion aceptada',
            mensaje=(
                f'{instance.instructor_invitado.username} ha aceptado tu invitacion '
                f'para ser jurado.'
            ),
            emisor=instance.instructor_invitado,
            url_relacionada=f'/evaluacion/',
        )
        _crear_notificacion(
            destinatario=instance.instructor_invitado,
            tipo=Notificacion.TIPO_ACEPTACION,
            titulo='Invitacion aceptada',
            mensaje='Has aceptado la invitacion para ser jurado.',
            url_relacionada=f'/usuarios/dashboard/jurado/',
        )

    elif instance.estado == Invitacion.ESTADO_RECHAZADA and instance.instructor and instance.instructor_invitado:
        emisor = instance.instructor_invitado
        _crear_notificacion(
            destinatario=instance.instructor,
            tipo=Notificacion.TIPO_RECHAZO,
            titulo='Invitacion rechazada',
            mensaje=(
                f'{emisor.username} ha rechazado '
                f'tu invitacion para ser jurado.'
            ),
            emisor=emisor,
            url_relacionada=f'/usuarios/instructores/',
        )


# ─────────────────────────────────────────────────────────────────────────────
# Signal: Evaluacion completada
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Evaluacion')
def evaluacion_completada(sender, instance, created, **kwargs):
    from apps.evaluacion.models import Evaluacion

    # Solo cuando se completa (no cuando se crea pendiente)
    if instance.estado == Evaluacion.ESTADO_COMPLETADA:
        # Notificar al aprendiz
        if instance.aprendiz and instance.aprendiz.usuario:
            _crear_notificacion(
                destinatario=instance.aprendiz.usuario,
                tipo=Notificacion.TIPO_RESULTADO,
                titulo='Evaluacion completada',
                mensaje=(
                    f'El jurado {instance.juror.username} ha completado tu evaluacion '
                    f'con calificacion total: {instance.calificacion_total}.'
                ),
                emisor=instance.juror,
                url_relacionada=f'/evaluacion/resultados/{instance.aprendiz_id}/',
            )


# ─────────────────────────────────────────────────────────────────────────────
# Signal: Resultado publicado
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Resultado')
def resultado_publicado(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.aprendiz and instance.aprendiz.usuario:
        _crear_notificacion(
            destinatario=instance.aprendiz.usuario,
            tipo=Notificacion.TIPO_RESULTADO,
            titulo='Resultado publicado',
            mensaje=(
                f'Tu resultado final ha sido registrado: '
                f'{instance.calificacion_final} (Promedio: {instance.promedio}).'
            ),
            url_relacionada=f'/evaluacion/resultados/{instance.id}/',
        )
