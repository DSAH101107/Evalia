from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q
import logging

from apps.evaluacion.models import Evaluacion, Resultado, Aprendiz, Invitacion
from apps.fichas.models import Ficha
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

    # --- 2) Fichas visibles para este instructor ---
    mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
    inv_fichas_ids = Invitacion.objects.filter(
        Q(instructor_invitado=request.user) | Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(inv_fichas_ids)
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(propietario_fichas)

    # --- 3) Evaluaciones y resultados (para la sección de tablas) ---
    # Solo mostrar datos de las fichas del instructor
    evaluaciones = (
        Evaluacion.objects.filter(aprendiz__ficha__id__in=mis_fichas_ids)
        .select_related('aprendiz', 'checklist', 'juror')
        .order_by('-fecha')
    )

    resultados = (
        Resultado.objects.filter(aprendiz__ficha__id__in=mis_fichas_ids)
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


