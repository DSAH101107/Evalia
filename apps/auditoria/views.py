# apps/auditoria/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.db.models import Count
from .models import LogAuditoria, BitacoraEvaluacion
from apps.usuarios.models import Usuario, Rol


@login_required
def bitacora_view(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    logs = LogAuditoria.objects.select_related('usuario').order_by('-created_at')[:200]
    return render(request, 'auditoria/bitacora.html', {'logs': logs})


@login_required
def bitacora_evaluacion(request, evaluacion_id):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    from apps.evaluacion.models import Evaluacion
    evaluacion = get_object_or_404(Evaluacion, pk=evaluacion_id)
    entradas = evaluacion.bitacora.select_related('modificado_por')
    return render(request, 'auditoria/bitacora_evaluacion.html', {
        'evaluacion': evaluacion,
        'entradas': entradas,
    })


@login_required
def api_resumen(request):
    if request.user.rol != 'administrador':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    hoy = LogAuditoria.objects.filter(created_at__date=timezone.now().date()).count()
    por_modulo = list(
        LogAuditoria.objects.values('modulo').annotate(total=Count('id')).order_by('-total')[:10]
    )
    por_accion = list(
        LogAuditoria.objects.values('accion').annotate(total=Count('id')).order_by('-total')[:10]
    )
    return JsonResponse({
        'hoy': hoy,
        'por_modulo': por_modulo,
        'por_accion': por_accion,
    })
