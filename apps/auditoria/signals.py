# apps/auditoria/signals.py
"""
Signals para registro automatico de log de auditoria.

Cada cambio en modelos importantes genera un LogAuditoria.
Los cambios se registran en:
  - post_save  → CREAR / EDITAR
  - post_delete → ELIMINAR
"""

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

Usuario = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_user(**kwargs):
    """Extrae el usuario desde instance o sender."""
    # Intentar por 'instance.usuario' (muchos modelos tienen FK a Usuario)
    for key in ('instance',):
        obj = kwargs.get(key)
        if obj is None:
            continue
        for attr in ('usuario', 'propietario', 'instructor', 'juror', 'emisor',
                      'destinatario', 'modificado_por'):
            val = getattr(obj, attr, None)
            if val is not None:
                return val
    return None


def _log(modulo, accion, descripcion='', obj=None, request=None):
    """Registra un LogAuditoria de forma segura."""
    try:
        from .models import LogAuditoria

        usuario = None
        if request is not None:
            usuario = getattr(request, 'user', None)
        if usuario is None and obj is not None:
            usuario = _get_user(instance=obj)

        ip = None
        ua = ''
        if request is not None:
            ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR')
            ua = request.META.get('HTTP_USER_AGENT', '')[:255]

        LogAuditoria.objects.create(
            usuario=usuario,
            modulo=modulo,
            accion=accion,
            descripcion=descripcion[:500],
            objeto_id=str(obj.pk) if obj and hasattr(obj, 'pk') and obj.pk else '',
            objeto_tipo=type(obj).__name__ if obj else '',
            ip_address=ip,
            user_agent=ua,
        )
    except Exception:
        logger.debug('No se pudo guardar log de auditoria', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# APRENDICES
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Aprendiz')
def aprendiz_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('aprendices', 'crear',
                  f'Aprendiz creado: {instance.nombres} {instance.apellidos} ({instance.documento})',
                  obj=instance)
        else:
            _log('aprendices', 'editar',
                  f'Aprendiz editado: {instance.nombres} {instance.apellidos} ({instance.documento})',
                  obj=instance)
        
        # Asignar competencias basadas en la fase cuando se crea o actualiza un aprendiz
        if instance.fase:
            from apps.evaluacion.models import Competencia, ChecklistItem
            from apps.competencias.models import Checklist
            
            # Obtener o crear un checklist por defecto para esta fase si no existe
            checklist_default, _ = Checklist.objects.get_or_create(
                titulo=f'Checklist Fase {instance.fase.numero}',
                defaults={'descripcion': f'Checklist automático para la fase {instance.fase.numero}'}
            )
            
            # Obtener competencias asociadas a la fase del aprendiz
            competencias_fase = Competencia.objects.filter(fase=instance.fase, activo=True)
            
            # Para cada competencia, asegurar que existen items en el checklist
            for competencia in competencias_fase:
                # Verificar si ya existe un checklistitem para esta competencia en el checklist
                item_existe = ChecklistItem.objects.filter(
                    checklist=checklist_default,
                    competencia=competencia
                ).exists()
                
                if not item_existe:
                    # Crear un item básico para esta competencia si no existe
                    ChecklistItem.objects.create(
                        checklist=checklist_default,
                        competencia=competencia,
                        criterio=f'Evaluación de {competencia.nombre}',
                        descripcion=f'Evaluar el desempeño en la competencia: {competencia.nombre}',
                        puntaje_maximo=10,
                        orden=0
                    )
    except Exception:
        logger.debug('No se pudo guardar log de auditoria o asignar competencias para aprendiz', exc_info=True)


@receiver(post_delete, sender='evaluacion.Aprendiz')
def aprendiz_delete(sender, instance, **kwargs):
    try:
        _log('aprendices', 'eliminar',
              f'Aprendiz eliminado: {instance.nombres} {instance.apellidos} ({instance.documento})',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de aprendiz', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='usuarios.Usuario')
def usuario_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('usuarios', 'crear',
                  f'Usuario creado: {instance.username} (rol={instance.rol})',
                  obj=instance)
        else:
            _log('usuarios', 'editar',
                  f'Usuario editado: {instance.username} (rol={instance.rol})',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para usuario', exc_info=True)


@receiver(post_delete, sender='usuarios.Usuario')
def usuario_delete(sender, instance, **kwargs):
    try:
        _log('usuarios', 'eliminar',
              f'Usuario eliminado: {instance.username}',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de usuario', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# INVITACIONES
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Invitacion')
def invitacion_save(sender, instance, created, **kwargs):
    try:
        from apps.evaluacion.models import Invitacion

        if created:
            _log('invitaciones', 'crear',
                  f'Invitacion enviada a {instance.instructor_invitado} por '
                  f'{instance.instructor} (fecha={instance.fecha_evaluacion})',
                  obj=instance)
        elif instance.estado == Invitacion.ESTADO_ACEPTADA:
            _log('invitaciones', 'aprobar',
                  f'Invitacion aceptada por {instance.instructor_invitado}',
                  obj=instance)
        elif instance.estado == Invitacion.ESTADO_RECHAZADA:
            _log('invitaciones', 'rechazar',
                  f'Invitacion rechazada por {instance.instructor_invitado}',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para invitacion', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# EVALUACIONES
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Evaluacion')
def evaluacion_save(sender, instance, created, **kwargs):
    try:
        from apps.evaluacion.models import Evaluacion

        if created:
            _log('evaluacion', 'iniciar_eval',
                  f'Evaluacion iniciada por {instance.juror} para '
                  f'{instance.aprendiz.nombres} {instance.aprendiz.apellidos}',
                  obj=instance)
        if instance.estado == Evaluacion.ESTADO_COMPLETADA:
            _log('evaluacion', 'finalizar_eval',
                  f'Evaluacion completada por {instance.juror} para '
                  f'{instance.aprendiz.nombres} {instance.aprendiz.apellidos} '
                  f'(calificacion={instance.calificacion_total})',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para evaluacion', exc_info=True)


@receiver(post_delete, sender='evaluacion.Evaluacion')
def evaluacion_delete(sender, instance, **kwargs):
    try:
        _log('evaluacion', 'eliminar',
              f'Evaluacion eliminada (id={instance.pk}, aprendiz={instance.aprendiz})',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de evaluacion', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Resultado')
def resultado_save(sender, instance, created, **kwargs):
    try:
        accion = 'crear' if created else 'editar'
        _log('resultados', accion,
              f'Resultado para {instance.aprendiz}: '
              f'{instance.calificacion_final} (promedio={instance.promedio})',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para resultado', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FICHAS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Ficha')
def ficha_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('fichas', 'crear',
                  f'Ficha creada: {instance.numero} ({instance.programa})',
                  obj=instance)
        else:
            _log('fichas', 'editar',
                  f'Ficha editada: {instance.numero}',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para ficha', exc_info=True)


@receiver(post_delete, sender='evaluacion.Ficha')
def ficha_delete(sender, instance, **kwargs):
    try:
        _log('fichas', 'eliminar',
              f'Ficha eliminada: {instance.numero}',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de ficha', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# COMPETENCIAS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Competencia')
def competencia_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('competencias', 'crear',
                  f'Competencia creada: {instance.codigo} - {instance.nombre}',
                  obj=instance)
        else:
            _log('competencias', 'editar',
                  f'Competencia editada: {instance.codigo} - {instance.nombre}',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para competencia', exc_info=True)


@receiver(post_delete, sender='evaluacion.Competencia')
def competencia_delete(sender, instance, **kwargs):
    try:
        _log('competencias', 'eliminar',
              f'Competencia eliminada: {instance.codigo} - {instance.nombre}',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de competencia', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# GAES
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.GAES')
def gaes_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('gaes', 'crear', f'GAES creado: {instance.nombre}', obj=instance)
        else:
            _log('gaes', 'editar', f'GAES editado: {instance.nombre}', obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para GAES', exc_info=True)


@receiver(post_delete, sender='evaluacion.GAES')
def gaes_delete(sender, instance, **kwargs):
    try:
        _log('gaes', 'eliminar', f'GAES eliminado: {instance.nombre}', obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de GAES', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRIMESTRES
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Trimestre')
def trimestre_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('trimestres', 'crear',
                  f'Trimestre creado: {instance}',
                  obj=instance)
        else:
            _log('trimestres', 'editar',
                  f'Trimestre editado: {instance}',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para trimestre', exc_info=True)


@receiver(post_delete, sender='evaluacion.Trimestre')
def trimestre_delete(sender, instance, **kwargs):
    try:
        _log('trimestres', 'eliminar', f'Trimestre eliminado: {instance}', obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de trimestre', exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# CHECKLISTS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='evaluacion.Checklist')
def checklist_save(sender, instance, created, **kwargs):
    try:
        if created:
            _log('checklists', 'crear',
                  f'Checklist creado: {instance.titulo}',
                  obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para checklist', exc_info=True)


@receiver(post_delete, sender='evaluacion.Checklist')
def checklist_delete(sender, instance, **kwargs):
    try:
        _log('checklists', 'eliminar',
              f'Checklist eliminado: {instance.titulo}',
              obj=instance)
    except Exception:
        logger.debug('No se pudo guardar log de auditoria para eliminación de checklist', exc_info=True)
