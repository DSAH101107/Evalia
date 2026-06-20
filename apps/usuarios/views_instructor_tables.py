from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
import logging

from apps.evaluacion.models import Evaluacion, Resultado, Aprendiz, Invitacion
from .models import Usuario

logger = logging.getLogger(__name__)


@login_required
def instructor_tablas(request):
    """Vista alternativa del panel del instructor (en formato “tablas”).

    Esta vista reutiliza la misma lógica del dashboard del instructor:
    - Limita acceso a administrador/instructor.
    - Calcula aprendices, evaluaciones y resultados asociados a jurados.
    - Lista invitaciones pendientes para el usuario autenticado.
    """
    # El panel del instructor se protege por permisos de rol.
    # Validación de permisos por rol

    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden('No tienes acceso a esta sección')

    # --- 1) Aprendices (listado y conteo) ---
    if request.user.rol == 'administrador':
        aprendices = Aprendiz.objects.all()
    else:
        aprendices = Aprendiz.objects.filter(propietario=request.user)
    total_aprendices = aprendices.count()

    # --- 2) Determinar jurados relacionados ---
    # En este sistema, el instructor ve datos que dependen de evaluaciones
    # realizadas por usuarios con rol='jurado'.
    jurados_relacionados = Usuario.objects.filter(rol='jurado').values_list('id', flat=True)

    # --- 3) Evaluaciones y resultados (para la sección de tablas) ---
    evaluaciones = (
        Evaluacion.objects.filter(juror__in=jurados_relacionados)
        .select_related('aprendiz', 'checklist', 'juror')
        .order_by('-fecha')
    )

    resultados = (
        Resultado.objects.filter(aprendiz__evaluaciones__juror__in=jurados_relacionados)
        .select_related('aprendiz')
        .distinct()
        .order_by('-fecha_cierre')
    )

    # --- 4) Invitaciones pendientes ---
    invitaciones = Invitacion.objects.filter(
        instructor_invitado=request.user,
        estado=Invitacion.ESTADO_PENDIENTE,
    )

    # --- 5) Render de plantilla con el contexto ---
    return render(
        request,
        'usuarios/dashboard_instructor_tablas.html',
        {
            'aprendices': aprendices,
            'total_aprendices': total_aprendices,
            'invitaciones': invitaciones,
            'evaluaciones': evaluaciones,
            'resultados': resultados,
        },
    )


