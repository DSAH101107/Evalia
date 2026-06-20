from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from .models import Notificacion


@login_required
def lista_notificaciones(request):
    """Lista las notificaciones del usuario autenticado."""
    notificaciones = Notificacion.objects.filter(
        destinatario=request.user
    ).select_related('emisor', 'destinatario')

    no_leidas = notificaciones.filter(estado=Notificacion.ESTADO_PENDIENTE).count()

    if request.method == 'POST':
        # Marcar como leída
        notif_id = request.POST.get('notif_id')
        if notif_id:
            try:
                notif = notificaciones.get(id=notif_id)
                notif.estado = Notificacion.ESTADO_LEIDA
                notif.fecha_leida = timezone.now()
                notif.save(update_fields=['estado', 'fecha_leida'])
            except Notificacion.DoesNotExist:
                pass

    return render(request, 'notificaciones/lista_notificaciones.html', {
        'notificaciones': notificaciones,
        'no_leidas': no_leidas,
    })


@login_required
def marcar_leida(request, notificacion_id):
    """Marca una notificación como leída via AJAX."""
    try:
        notificacion = Notificacion.objects.get(
            id=notificacion_id,
            destinatario=request.user,
        )
        notificacion.estado = Notificacion.ESTADO_LEIDA
        notificacion.fecha_leida = timezone.now()
        notificacion.save(update_fields=['estado', 'fecha_leida'])
        return JsonResponse({'success': True})
    except Notificacion.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No encontrada'}, status=404)


@login_required
def notificaciones_api(request):
    """Endpoint JSON con conteo de notificaciones no leídas (para badge en navbar)."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    no_leidas = Notificacion.objects.filter(
        destinatario=request.user,
        estado=Notificacion.ESTADO_PENDIENTE,
    ).count()

    ultimas = Notificacion.objects.filter(
        destinatario=request.user,
    ).select_related('emisor').order_by('-fecha_envio')[:5]

    data = {
        'no_leidas': no_leidas,
        'ultimas': [
            {
                'id': n.id,
                'titulo': n.titulo,
                'tipo': n.tipo,
                'estado': n.estado,
                'fecha_envio': n.fecha_envio.strftime('%d/%m/%Y %H:%M'),
                'url_relacionada': n.url_relacionada,
            }
            for n in ultimas
        ],
    }
    return JsonResponse(data)
