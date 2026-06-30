from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db import models
from django.db.models import OuterRef, Subquery, Q, Count, Sum, Case, When, IntegerField
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.db import transaction
from django.conf import settings
from django.utils import timezone
import logging
import io
import re
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors as rl_colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .models import (
    Evaluacion, EvaluacionItem, Resultado, Invitacion,
    Aprendiz, Checklist, ChecklistItem,
)
from apps.gaes.models import GAES
from apps.fichas.models import Ficha
from apps.trimestres.models import Trimestre
from apps.competencias.models import Fase, Competencia
from apps.usuarios.models import Usuario, Rol
from io import BytesIO

CHECKLIST_PERMISOS = ['administrador', 'instructor', 'jurado']

def home(request):
    if not request.user.is_authenticated:
        return redirect('login_view')
    if request.user.rol == 'administrador' or request.user.is_superuser:
        return redirect('dashboard_admin')
    elif request.user.rol == 'instructor':
        return redirect('dashboard_instructor')
    elif request.user.rol == 'jurado':
        return redirect('dashboard_jurado')
    elif request.user.rol == 'aprendiz':
        return redirect('dashboard_aprendiz')
    else:
        return redirect('lista_aprendices')

def lista_checklists(request):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    
    if request.user.rol == 'jurado':
        ficha_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        checklists = Checklist.objects.filter(
            activo=True,
            invitaciones__ficha_id__in=ficha_ids
        ).distinct().order_by('-id')
    elif request.user.rol == 'instructor':
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
        checklists = Checklist.objects.filter(
            activo=True
        ).filter(
            Q(propietario=request.user) |
            Q(items__competencia__ficha_id__in=mis_fichas_ids)
        ).distinct().order_by('-id')
    else:
        checklists = Checklist.objects.filter(activo=True).order_by('-id')

    # Filtros multicriterio
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_activo = request.GET.get('filtro_activo', '')
    search = request.GET.get('search', '')

    if search:
        checklists = checklists.filter(
            models.Q(titulo__icontains=search)
            | models.Q(descripcion__icontains=search)
        )
    if filtro_titulo:
        checklists = checklists.filter(titulo__icontains=filtro_titulo)
    if filtro_activo:
        checklists = checklists.filter(activo=filtro_activo == 'true')

    return render(request, 'evaluacion/lista_checklists.html', {
        'checklists': checklists,
        'filtro_titulo': filtro_titulo,
        'filtro_activo': filtro_activo,
        'search': search,
    })

@login_required
def crear_checklist(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        checklist = Checklist.objects.create(
            titulo=titulo or 'Checklist sin título',
            descripcion=descripcion,
            activo=True,
            propietario=request.user,
        )
        criterios = request.POST.getlist('criterio')
        puntajes = request.POST.getlist('puntaje_maximo')
        descripciones = request.POST.getlist('descripcion')
        etapas = request.POST.getlist('etapa')
        for i, criterio in enumerate(criterios):
            puntaje = puntajes[i] if i < len(puntajes) else 10
            descripcion = descripciones[i] if i < len(descripciones) else ''
            etapa = etapas[i] if i < len(etapas) else ''
            try:
                puntaje = int(puntaje)
            except (ValueError, TypeError):
                puntaje = 10
            ChecklistItem.objects.create(
                checklist=checklist,
                competencia=None,
                criterio=criterio,
                descripcion=descripcion,
                puntaje_maximo=puntaje,
                orden=i,
                etapa=etapa,
            )
        messages.success(request, 'Checklist creada.')
        return redirect('lista_checklists')
    all_competencias = Competencia.objects.order_by('codigo')
    return render(request, 'evaluacion/crear_checklist.html', {
        'all_competencias': all_competencias,
    })

@login_required
def eliminar_checklist(request, checklist_id):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        checklist = get_object_or_404(Checklist, pk=checklist_id)
        if request.user.rol != 'administrador' and checklist.propietario != request.user:
            return HttpResponseForbidden('No tienes permiso para eliminar este checklist')
        checklist.delete()
        return JsonResponse({'success': True, 'message': 'Checklist eliminada.'})
    return HttpResponseForbidden()

@login_required
def ver_editar_checklist(request, checklist_id):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    if request.user.rol != 'administrador' and checklist.propietario != request.user:
        return HttpResponseForbidden('No tienes acceso a este checklist')
    items = checklist.items.order_by('orden')
    can_edit = request.user.rol in ['administrador', 'instructor']
    if request.method == 'POST' and can_edit:
        for item in items:
            criterio_key = f'criterio_{item.id}'
            puntaje_key  = f'puntaje_maximo_{item.id}'
            desc_key     = f'descripcion_{item.id}'
            if criterio_key in request.POST:
                item.criterio = request.POST.get(criterio_key, item.criterio)
            if puntaje_key in request.POST:
                try:
                    item.puntaje_maximo = int(float(request.POST.get(puntaje_key, item.puntaje_maximo)))
                except (ValueError, TypeError):
                    pass
            if desc_key in request.POST:
                item.descripcion = request.POST.get(desc_key, item.descripcion)
            item.save()
        messages.success(request, 'Checklist actualizada.')
        return redirect('ver_editar_checklist', checklist_id=checklist_id)
    all_competencias = Competencia.objects.order_by('codigo')
    return render(request, 'evaluacion/ver_editar_checklist.html', {
        'checklist': checklist,
        'items': items,
        'can_edit': can_edit,
        'all_competencias': all_competencias,
    })

@login_required
def imprimir_checklist(request, checklist_id):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    if request.user.rol != 'administrador' and checklist.propietario != request.user:
        return HttpResponseForbidden('No tienes acceso a este checklist')
    items = checklist.items.order_by('orden')
    return render(request, 'evaluacion/imprimir_checklist.html', {
        'checklist': checklist,
        'items': items,
        'can_edit': False,
    })

@login_required
def iniciar_evaluacion(request, aprendiz_id):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')
    aprendiz = get_object_or_404(Aprendiz, id=aprendiz_id)
    
    if request.user.rol == 'jurado':
        ficha_id = aprendiz.ficha_id or (aprendiz.gaes.ficha_id if aprendiz.gaes else None)
        if ficha_id:
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                ficha_id=ficha_id,
                estado=Invitacion.ESTADO_ACEPTADA
            ).exists()
            if not has_access:
                return HttpResponseForbidden('No tienes acceso a este aprendiz')
    
    if aprendiz.fase:
        checklists = Checklist.objects.filter(
            activo=True,
            items__competencia__fase=aprendiz.fase
        ).distinct()
    else:
        if request.user.rol == 'administrador':
            checklists = Checklist.objects.filter(activo=True)
        elif request.user.rol == 'instructor':
            mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
            inv_fichas_ids = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                estado=Invitacion.ESTADO_ACEPTADA
            ).values_list('ficha_id', flat=True).distinct()
            mis_fichas_ids |= set(inv_fichas_ids)
            propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
            mis_fichas_ids |= set(propietario_fichas)
            checklists = Checklist.objects.filter(
                activo=True,
                items__competencia__ficha_id__in=mis_fichas_ids
            ).distinct()
        elif request.user.rol == 'jurado':
            ficha_ids = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                estado=Invitacion.ESTADO_ACEPTADA
            ).values_list('ficha_id', flat=True).distinct()
            checklists = Checklist.objects.filter(
                activo=True,
                items__competencia__ficha_id__in=ficha_ids
            ).distinct()
        else:
            checklists = Checklist.objects.none()
    if request.method == 'POST':
        checklist_id = request.POST.get('checklist_id')
        if checklist_id:
            checklist = get_object_or_404(Checklist, id=checklist_id, activo=True)
            if request.user.rol != 'administrador' and checklist.propietario != request.user:
                return HttpResponseForbidden('No tienes acceso a este checklist')
            evaluacion = Evaluacion.objects.create(
                aprendiz=aprendiz,
                juror=request.user,
                checklist=checklist,
                estado='pendiente'
            )
            return redirect('evaluar_aprendiz', evaluacion_id=evaluacion.id)
    return render(request, 'evaluacion/iniciar_evaluacion.html', {
        'aprendiz': aprendiz,
        'checklists': checklists,
    })

@login_required
def evaluar_aprendiz(request, evaluacion_id):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')
    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    if evaluacion.juror != request.user and request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta evaluación')
    items = evaluacion.checklist.items.order_by('orden')
    if request.method == 'POST':
        for item in items:
            puntaje_key = f'puntaje_{item.id}'
            observaciones_key = f'observaciones_{item.id}'
            puntaje = request.POST.get(puntaje_key, '0')
            observaciones = request.POST.get(observaciones_key, '')
            ev_item, _ = EvaluacionItem.objects.update_or_create(
                evaluacion=evaluacion,
                item=item,
                defaults={
                    'puntaje': int(puntaje) if puntaje else 0,
                    'observaciones': observaciones,
                }
            )
        evaluacion.calcular_puntaje()
        evaluacion.estado = Evaluacion.ESTADO_COMPLETADA
        evaluacion.save(update_fields=['calificacion_total', 'estado'])

        items_qs = EvaluacionItem.objects.filter(evaluacion=evaluacion)
        total_items = items_qs.count()
        items_aprobados = items_qs.filter(puntaje__gt=0).count()

        resultado, _ = Resultado.objects.get_or_create(aprendiz=evaluacion.aprendiz)
        if total_items > 0 and items_aprobados == total_items:
            resultado.calificacion_final = 'Cumplió'
            resultado.promedio = 100
        else:
            resultado.calificacion_final = 'No cumplió'
            resultado.promedio = items_qs.aggregate(
                total=models.Sum('puntaje')
            )['total'] or 0
        resultado.save()

        gaes_actual = evaluacion.aprendiz.gaes
        siguiente = None
        if gaes_actual:
            siguiente = Evaluacion.objects.filter(
                aprendiz__gaes=gaes_actual,
                estado=Evaluacion.ESTADO_PENDIENTE,
            ).exclude(id=evaluacion.id).order_by('id').first()
        if siguiente:
            messages.info(request, f'Siguiente: {siguiente.aprendiz.nombres} {siguiente.aprendiz.apellidos}')
            return redirect('evaluar_aprendiz', evaluacion_id=siguiente.id)
        messages.success(request, 'Evaluación guardada.')
        return redirect('lista_evaluaciones')
    return render(request, 'evaluacion/evaluar_aprendiz.html', {
        'evaluacion': evaluacion,
        'items': items,
    })

@login_required
def aceptar_invitacion(request, invitacion_id):
    invitacion = get_object_or_404(Invitacion, id=invitacion_id)
    if invitacion.estado != Invitacion.ESTADO_PENDIENTE:
        messages.error(request, 'La invitación ya fue respondida.')
        return redirect('invitaciones_jurado')
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden()
    invitacion.estado = Invitacion.ESTADO_ACEPTADA
    invitacion.instructor_invitado = request.user
    invitacion.fecha_respuesta = timezone.now()
    invitacion.save()
    if request.user.rol != 'jurado':
        request.user.rol = 'jurado'
        request.user.save(update_fields=['rol'])
    messages.success(request, 'Invitación aceptada.')
    return redirect('invitaciones_jurado')

@login_required
def rechazar_invitacion(request, invitacion_id):
    invitacion = get_object_or_404(Invitacion, id=invitacion_id)
    if invitacion.estado != Invitacion.ESTADO_PENDIENTE:
        messages.error(request, 'La invitación ya fue respondida.')
        return redirect('invitaciones_jurado')
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden()
    invitacion.estado = Invitacion.ESTADO_RECHAZADA
    invitacion.fecha_respuesta = timezone.now()
    invitacion.save()
    messages.info(request, 'Invitación rechazada.')
    return redirect('invitaciones_jurado')

@login_required
def ver_checklist_limpio(request, checklist_id):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    
    if request.user.rol == 'jurado':
        ficha_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        has_access = Checklist.objects.filter(
            pk=checklist_id,
            items__competencia__ficha_id__in=ficha_ids
        ).exists()
        if not has_access:
            return HttpResponseForbidden()
    elif request.user.rol == 'instructor':
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
        has_access = Checklist.objects.filter(
            pk=checklist_id
        ).filter(
            Q(items__competencia__ficha_id__in=mis_fichas_ids) |
            Q(items__competencia__isnull=True) |
            Q(items__isnull=True)
        ).exists()
        if not has_access:
            return HttpResponseForbidden()
    
    items = checklist.items.order_by('orden')
    return render(request, 'evaluacion/ver_checklist_limpio.html', {
        'checklist': checklist,
        'items': items,
    })

@login_required
def enviar_invitacion(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.user.rol == 'administrador':
        fichas = Ficha.objects.all().order_by('numero')
        checklists = Checklist.objects.filter(activo=True).order_by('titulo')
    else:
        fichas = Ficha.objects.filter(instructor=request.user).order_by('numero')
        checklists = Checklist.objects.filter(activo=True, propietario=request.user).order_by('titulo')
    instructores = Usuario.objects.filter(rol='instructor').exclude(id=request.user.id)
    if request.method == 'POST':
        ficha_id = request.POST.get('ficha')
        jurados_ids = request.POST.getlist('jurados')
        fecha = request.POST.get('fecha_evaluacion')
        hora = request.POST.get('hora_evaluacion')
        mensaje = request.POST.get('mensaje', '')
        checklist_id = request.POST.get('checklist_id')
        ficha = get_object_or_404(Ficha, id=ficha_id) if ficha_id else None
        checklist = get_object_or_404(Checklist, id=checklist_id) if checklist_id else None
        if checklist and request.user.rol != 'administrador' and checklist.propietario != request.user:
            return HttpResponseForbidden('No tienes acceso a este checklist')
        invitacion = Invitacion.objects.create(
            instructor=request.user,
            ficha=ficha,
            checklist=checklist,
            fecha_evaluacion=fecha,
            hora_evaluacion=hora,
            mensaje=mensaje,
            estado=Invitacion.ESTADO_PENDIENTE,
        )
        for jurado_id in jurados_ids:
            jurado = get_object_or_404(Usuario, id=jurado_id)
            invitacion.instructores_jurados.add(jurado)
        messages.success(request, 'Invitación enviada.')
        return redirect('enviar_invitacion')
    return render(request, 'evaluacion/enviar_invitacion.html', {
        'fichas': fichas,
        'instructores': instructores,
        'checklists': checklists,
    })

@login_required
def invitaciones_jurado(request):
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden()
    invitaciones = Invitacion.objects.filter(
        Q(instructor=request.user) | Q(instructores_jurados=request.user)
    ).distinct().order_by('-fecha_envio')
    return render(request, 'evaluacion/invitaciones_jurado.html', {
        'invitaciones': invitaciones,
    })

@login_required
def lista_aprendices(request):
    if request.user.rol not in CHECKLIST_PERMISOS + ['jefe']:
        return HttpResponseForbidden()
    
    # Base query - filter by invitation for jurado
    if request.user.rol == 'jurado':
        # Jurado: only aprendices from fichas where they were invited
        ficha_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        aprendices = Aprendiz.objects.filter(
            Q(ficha_id__in=ficha_ids) | Q(gaes__ficha_id__in=ficha_ids)
        ).select_related('ficha', 'gaes', 'fase').distinct()
    elif request.user.rol == 'administrador' or request.user.is_superuser:
        aprendices = Aprendiz.objects.all().select_related('ficha', 'gaes', 'fase')
    elif request.user.rol == 'jefe':
        aprendices = Aprendiz.objects.all().select_related('ficha', 'gaes', 'fase')
    else:
        # Instructor: ver aprendices de sus fichas asignadas, del GAES de esas fichas
        # y de aprendices donde él es propietario.
        fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        aprendices = Aprendiz.objects.filter(
            models.Q(ficha_id__in=fichas_ids)
            | models.Q(gaes__ficha_id__in=fichas_ids)
            | models.Q(propietario=request.user)
        ).select_related('ficha', 'gaes', 'gaes__ficha', 'fase').distinct()
    
    # Get filter values
    filtro_documento = request.GET.get('filtro_documento', '')
    filtro_nombre = request.GET.get('filtro_nombre', '')
    filtro_email = request.GET.get('filtro_email', '')
    filtro_ficha = request.GET.get('filtro_ficha', '')
    filtro_gaes = request.GET.get('filtro_gaes', '')
    filtro_fase = request.GET.get('filtro_fase', '')
    solo_bloqueados = request.GET.get('solo_bloqueados', '')
    search = request.GET.get('search', '')
    
    # Apply filters
    if search:
        aprendices = aprendices.filter(
            models.Q(nombres__icontains=search)
            | models.Q(documento__icontains=search)
        )
    if filtro_documento:
        aprendices = aprendices.filter(documento__icontains=filtro_documento)
    if filtro_nombre:
        aprendices = aprendices.filter(nombres__icontains=filtro_nombre)
    if filtro_email:
        aprendices = aprendices.filter(email__icontains=filtro_email)
    if filtro_ficha:
        aprendices = aprendices.filter(ficha__numero=filtro_ficha)
    if filtro_gaes:
        aprendices = aprendices.filter(gaes__nombre=filtro_gaes)
    if filtro_fase:
        aprendices = aprendices.filter(fase__numero=filtro_fase)
    if solo_bloqueados == '1':
        aprendices = aprendices.filter(bloqueado=True)
    
    aprendices = aprendices.order_by('nombres')
    
    # Context for filters
    if request.user.rol == 'administrador' or request.user.is_superuser:
        fichas_list = Ficha.objects.all().order_by('numero')
    elif request.user.rol == 'instructor':
        fichas_list = Ficha.objects.filter(instructor=request.user).order_by('numero')
    elif request.user.rol == 'jurado':
        ficha_ids = Invitacion.objects.filter(
            Q(instructor_invitado=request.user) | Q(instructores_jurados=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        fichas_list = Ficha.objects.filter(id__in=ficha_ids).order_by('numero')
    else:
        fichas_list = Ficha.objects.none()
    
    if request.user.rol == 'administrador' or request.user.is_superuser:
        gaes_list = GAES.objects.all().order_by('nombre')
        fases_list = Fase.objects.all().order_by('numero')
    elif request.user.rol in ['instructor', 'jurado']:
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructor_invitado=request.user) | Q(instructores_jurados=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
        gaes_list = GAES.objects.filter(fichas__id__in=mis_fichas_ids).distinct().order_by('nombre')
        fases_list = Fase.objects.filter(competencias__ficha_id__in=mis_fichas_ids).distinct().order_by('numero')
    else:
        gaes_list = GAES.objects.none()
        fases_list = Fase.objects.none()
    
    return render(request, 'evaluacion/lista_aprendices.html', {
        'aprendices': aprendices,
        'search': search,
        'filtro_documento': filtro_documento,
        'filtro_nombre': filtro_nombre,
        'filtro_email': filtro_email,
        'filtro_ficha': filtro_ficha,
        'filtro_gaes': filtro_gaes,
        'filtro_fase': filtro_fase,
        'solo_bloqueados': solo_bloqueados,
        'fichas_list': fichas_list,
        'gaes_list': gaes_list,
        'fases_list': fases_list,
        'total_aprendices': aprendices.count(),
    })

@login_required
def crear_aprendiz(request):
    if request.user.rol not in ['administrador', 'instructor', 'jefe']:
        return HttpResponseForbidden()
    if request.user.rol == 'administrador':
        fichas = Ficha.objects.all().order_by('numero')
    elif request.user.rol == 'instructor':
        fichas = Ficha.objects.filter(instructor=request.user).order_by('numero')
    else:
        fichas = Ficha.objects.none()
    if request.method == 'POST':
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            nombres = request.POST.get('nombres', '').strip()
            documento = request.POST.get('documento', '').strip()
            email = request.POST.get('email', '').strip()
            telefono = request.POST.get('telefono', '')
            ficha_id = request.POST.get('ficha')
            gaes_id = request.POST.get('gaes')
            fase_id = request.POST.get('fase')
            usuario_creado = None
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if email:
                username = email.split('@')[0]
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                usuario_creado = User.objects.create_user(
                    username=username,
                    email=email,
                    rol='aprendiz',
                    password=Usuario.objects.make_random_password(),
                )
            ficha = Ficha.objects.get(id=ficha_id) if ficha_id else None
            gaes = GAES.objects.get(id=gaes_id) if gaes_id else None
            fase = Fase.objects.get(id=fase_id) if fase_id else None
            aprendiz = Aprendiz.objects.create(
                nombres=nombres,
                documento=documento,
                email=email,
                telefono=telefono,
                ficha=ficha,
                gaes=gaes,
                fase=fase,
                usuario=usuario_creado,
                propietario=request.user,
            )
        messages.success(request, 'Aprendiz creado.')
        return redirect('lista_aprendices')
    return render(request, 'evaluacion/crear_aprendiz.html', {
        'fichas': fichas,
    })

@login_required
def editar_aprendiz(request, aprendiz_id):
    aprendiz = get_object_or_404(Aprendiz, id=aprendiz_id)
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.user.rol == 'administrador':
        fichas = Ficha.objects.all().order_by('numero')
    elif request.user.rol == 'instructor':
        fichas = Ficha.objects.filter(instructor=request.user).order_by('numero')
    else:
        fichas = Ficha.objects.none()
    if request.method == 'POST':
        aprendiz.nombres = request.POST.get('nombres', aprendiz.nombres).strip()
        aprendiz.documento = request.POST.get('documento', aprendiz.documento).strip()
        aprendiz.email = request.POST.get('email', aprendiz.email).strip()
        aprendiz.telefono = request.POST.get('telefono', aprendiz.telefono)
        ficha_id = request.POST.get('ficha')
        if ficha_id:
            aprendiz.ficha_id = ficha_id
        else:
            aprendiz.ficha = None
        gaes_id = request.POST.get('gaes')
        if gaes_id:
            aprendiz.gaes_id = gaes_id
        else:
            aprendiz.gaes = None
        fase_id = request.POST.get('fase')
        if fase_id:
            aprendiz.fase_id = fase_id
        else:
            aprendiz.fase = None
        aprendiz.save()
        messages.success(request, 'Aprendiz actualizado.')
        return redirect('lista_aprendices')
    return render(request, 'evaluacion/editar_aprendiz.html', {
        'aprendiz': aprendiz,
        'fichas': fichas,
    })

@login_required
def importar_excel(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        from django.db import transaction as db_transaction
        archivo = request.FILES.get('archivo_excel')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo.')
            return redirect('importar_excel')
        default_ficha_id = request.POST.get('default_ficha')
        default_fase_val = request.POST.get('default_fase')
        default_ficha = None
        if default_ficha_id:
            try:
                default_ficha = Ficha.objects.get(id=default_ficha_id)
            except Ficha.DoesNotExist:
                pass
        default_fase = None
        if default_fase_val:
            default_fase, _ = Fase.objects.get_or_create(numero=default_fase_val)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        with db_transaction.atomic():
            df = pd.read_excel(archivo)
            col_map = {}
            for col in df.columns:
                c = str(col).lower().strip()
                if 'documento' in c or c in ('doc', 'cedula', 'cc', 'nit'):
                    col_map['documento'] = col
                elif 'nombre' in c and 'apellido' not in c:
                    col_map['nombre'] = col
                elif 'apellido' in c:
                    col_map['apellidos'] = col
                elif 'email' in c or 'correo' in c or 'e-mail' in c or 'mail' in c:
                    col_map['email'] = col
                elif 'telefono' in c or 'tel' in c:
                    col_map['telefono'] = col
                elif 'ficha' in c:
                    col_map['ficha'] = col
                elif 'gaes' in c:
                    col_map['gaes'] = col
                elif 'fase' in c:
                    col_map['fase'] = col
                elif 'trimestre' in c:
                    col_map['trimestre'] = col

            def _val(row, key):
                val = row.get(col_map.get(key, ''))
                return str(val).strip() if val is not None else ''

            for _, row in df.iterrows():
                nombre = _val(row, 'nombre')
                documento = _val(row, 'documento')
                apellidos = _val(row, 'apellidos')
                email = _val(row, 'email')
                telefono = _val(row, 'telefono')
                ficha_col = _val(row, 'ficha')
                fase_col = _val(row, 'fase')
                trimestre = _val(row, 'trimestre')
                if not nombre or not documento:
                    continue
                nombres_completos = nombre
                if apellidos:
                    nombres_completos = f"{nombre} {apellidos}"
                ficha_obj = default_ficha
                if ficha_col:
                    ficha_obj, _ = Ficha.objects.get_or_create(numero=ficha_col)
                gaes_obj = None  # No asignar GAES automáticamente
                fase_obj = default_fase
                if fase_col:
                    fase_obj, _ = Fase.objects.get_or_create(numero=fase_col)
                usuario_creado = None
                if email and '@' in email:
                    username = re.sub(r'[^a-zA-Z0-9._-]', '', email.split('@')[0])
                    base_username = username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    usuario_creado = User.objects.create_user(
                        username=username,
                        email=email,
                        rol='aprendiz',
                        password=Usuario.objects.make_random_password(),
                    )
                aprendiz, created = Aprendiz.objects.update_or_create(
                    documento=documento,
                    defaults={
                        'nombres': nombres_completos,
                        'email': email,
                        'telefono': telefono,
                        'ficha': ficha_obj,
                        'gaes': gaes_obj,
                        'fase': fase_obj,
                        'usuario': usuario_creado,
                        'propietario': request.user,
                    }
                )
        messages.success(request, f'{len(df)} aprendices importados.')
        return redirect('lista_aprendices')
    return render(request, 'evaluacion/importar_excel.html', {
            'fichas_list': fichas_list,
            'fases': Fase.objects.order_by('numero'),
        })

@login_required
def importar_excel_asignar_gaes(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo.')
            return redirect('importar_excel_asignar_gaes')
        df = pd.read_excel(archivo)
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            for _, row in df.iterrows():
                documento = str(row.iloc[0]).strip() if len(row) > 0 else ''
                gaes_id = row.iloc[1] if len(row) > 1 else None
                try:
                    aprendiz = Aprendiz.objects.get(documento=documento)
                    if gaes_id:
                        aprendiz.gaes = get_object_or_404(GAES, id=gaes_id)
                    aprendiz.save()
                except Aprendiz.DoesNotExist:
                    continue
        messages.success(request, 'GAES actualizado para aprendices.')
        return redirect('lista_aprendices')
    return render(request, 'evaluacion/importar_excel_asignar_gaes.html')

@login_required
def importar_csv_aprendices(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        archivo = request.FILES.get('archivo_csv')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo.')
            return redirect('importar_csv_aprendices')
        default_ficha_id = request.POST.get('default_ficha')
        default_fase_val = request.POST.get('default_fase')
        default_ficha = None
        if default_ficha_id:
            try:
                default_ficha = Ficha.objects.get(id=default_ficha_id)
            except Ficha.DoesNotExist:
                pass
        default_fase = None
        if default_fase_val:
            default_fase, _ = Fase.objects.get_or_create(numero=default_fase_val)
        from django.db import transaction as db_transaction
        from django.contrib.auth import get_user_model
        User = get_user_model()
        with db_transaction.atomic():
            contenido = archivo.read()
            df = None
            for sep in [',', ';', '\t']:
                try:
                    archivo.seek(0)
                    df = pd.read_csv(archivo, encoding='utf-8-sig', sep=sep)
                    if len(df.columns) >= 3:
                        break
                    df = None
                except Exception:
                    archivo.seek(0)
                    continue
            if df is None:
                messages.error(request, 'No se pudo leer el archivo CSV. Verifica el formato.')
                return redirect('importar_csv_aprendices')
            col_map = {}
            for col in df.columns:
                c = col.lower().strip()
                if 'documento' in c or c in ('doc', 'cedula', 'cc', 'nit'):
                    col_map['documento'] = col
                elif 'nombre' in c and 'apellido' not in c:
                    col_map['nombre'] = col
                elif 'apellido' in c:
                    col_map['apellidos'] = col
                elif 'email' in c or 'correo' in c or 'e-mail' in c or 'mail' in c:
                    col_map['email'] = col
                elif 'telefono' in c or 'tel' in c:
                    col_map['telefono'] = col
                elif 'ficha' in c:
                    col_map['ficha'] = col
                elif 'fase' in c:
                    col_map['fase'] = col
                elif 'trimestre' in c:
                    col_map['trimestre'] = col
            for _, row in df.iterrows():
                nombre = str(row.get(col_map.get('nombre', ''), '')).strip()
                documento = str(row.get(col_map.get('documento', ''), '')).strip()
                apellidos = str(row.get(col_map.get('apellidos', ''), '')).strip()
                email = str(row.get(col_map.get('email', ''), '')).strip()
                telefono = str(row.get(col_map.get('telefono', ''), '')).strip()
                ficha_col = str(row.get(col_map.get('ficha', ''), '')).strip()
                fase_col = str(row.get(col_map.get('fase', ''), '')).strip()
                trimestre = str(row.get(col_map.get('trimestre', ''), '')).strip()
                if not nombre or not documento:
                    continue
                nombres_completos = nombre
                if apellidos:
                    nombres_completos = f"{nombre} {apellidos}"
                ficha_obj = default_ficha
                if ficha_col:
                    ficha_obj, _ = Ficha.objects.get_or_create(numero=ficha_col)
                gaes_obj = None  # No asignar GAES automáticamente
                fase_obj = default_fase
                if fase_col:
                    fase_obj, _ = Fase.objects.get_or_create(numero=fase_col)
                usuario_creado = None
                if email and '@' in email:
                    username = re.sub(r'[^a-zA-Z0-9._-]', '', email.split('@')[0])
                    base_username = username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    usuario_creado = User.objects.create_user(
                        username=username,
                        email=email,
                        rol='aprendiz',
                        password=Usuario.objects.make_random_password(),
                    )
                Aprendiz.objects.update_or_create(
                    documento=documento,
                    defaults={
                        'nombres': nombres_completos,
                        'email': email,
                        'telefono': telefono,
                        'ficha': ficha_obj,
                        'gaes': gaes_obj,
                        'fase': fase_obj,
                        'usuario': usuario_creado,
                        'propietario': request.user,
                    }
                )
        messages.success(request, 'CSV importado.')
        return redirect('lista_aprendices')
    if request.user.rol == 'administrador':
        fichas_list = Ficha.objects.all().order_by('numero')
    else:
        fichas_list = Ficha.objects.filter(instructor=request.user).order_by('numero')
    return render(request, 'evaluacion/importar_csv_aprendices.html', {
        'fichas_list': fichas_list,
        'fases': Fase.objects.order_by('numero'),
    })

@login_required
def bloquear_aprendiz(request, aprendiz_id):
    aprendiz = get_object_or_404(Aprendiz, id=aprendiz_id)
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    aprendiz.bloqueado = True
    aprendiz.save(update_fields=['bloqueado'])
    messages.info(request, 'Aprendiz bloqueado.')
    return redirect('lista_aprendices')

@login_required
def eliminar_aprendiz_post(request, aprendiz_id):
    aprendiz = get_object_or_404(Aprendiz, id=aprendiz_id)
    if request.user.rol not in ['administrador']:
        return HttpResponseForbidden()
    aprendiz.delete()
    messages.success(request, 'Aprendiz eliminado.')
    return redirect('lista_aprendices')

@login_required
def lista_evaluaciones(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden()
    
    if request.user.rol == 'jurado':
        fichas = Ficha.objects.filter(
            Q(invitaciones__instructores_jurados=request.user) |
            Q(invitaciones__instructor_invitado=request.user),
            invitaciones__estado=Invitacion.ESTADO_ACEPTADA
        ).distinct().order_by('numero')
    elif request.user.rol == 'instructor':
        fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        fichas_ids |= set(propietario_fichas)
        fichas = Ficha.objects.filter(id__in=fichas_ids).order_by('numero')
    else:
        fichas = Ficha.objects.all().order_by('numero')
    
    # Filtros multicriterio
    filtro_numero = request.GET.get('filtro_numero', '')
    filtro_programa = request.GET.get('filtro_programa', '')
    filtro_estado = request.GET.get('filtro_estado', '')
    search = request.GET.get('search', '')
    
    if search:
        fichas = fichas.filter(
            Q(numero__icontains=search) |
            Q(programa__icontains=search)
        )
    if filtro_numero:
        fichas = fichas.filter(numero__icontains=filtro_numero)
    if filtro_programa:
        fichas = fichas.filter(programa__icontains=filtro_programa)
    
    # Annotate with evaluation counts
    for ficha in fichas:
        aprendices_ids = ficha.aprendices.values_list('id', flat=True)
        completadas = Evaluacion.objects.filter(
            aprendiz_id__in=aprendices_ids,
            estado=Evaluacion.ESTADO_COMPLETADA
        ).count()
        ficha.evaluaciones_completadas = completadas
    
    return render(request, 'evaluacion/lista_evaluaciones.html', {
        'fichas': fichas,
        'filtro_numero': filtro_numero,
        'filtro_programa': filtro_programa,
        'filtro_estado': filtro_estado,
        'search': search,
    })


@login_required
def detalle_ficha_evaluacion(request, ficha_id):
    ficha = get_object_or_404(Ficha, id=ficha_id)
    if request.user.rol not in ['administrador', 'jurado', 'instructor', 'aprendiz']:
        return HttpResponseForbidden()
    
    if request.user.rol == 'jurado':
        has_access = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            ficha=ficha,
            estado=Invitacion.ESTADO_ACEPTADA
        ).exists()
        if not has_access:
            return HttpResponseForbidden("No tienes acceso a esta ficha")
    elif request.user.rol == 'instructor':
        has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
        if not has_access:
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                ficha_id=ficha_id,
                estado=Invitacion.ESTADO_ACEPTADA
            ).exists()
        if not has_access:
            has_access = Aprendiz.objects.filter(ficha_id=ficha_id, propietario=request.user).exists()
        if not has_access:
            return HttpResponseForbidden("No tienes acceso a esta ficha")
    
    # Get all GAES in this ficha
    gaes_list = GAES.objects.filter(ficha=ficha).prefetch_related(
        'aprendices', 'aprendices__resultados'
    ).distinct()
    
    # Get jurados who evaluated this ficha
    jurados_ficha = Usuario.objects.filter(
        evaluaciones_realizadas__aprendiz__gaes__ficha=ficha
    ).distinct()
    
    # Add evaluation status to each GAES
    for g in gaes_list:
        items = EvaluacionItem.objects.filter(
            evaluacion__aprendiz__gaes=g,
            evaluacion__estado=Evaluacion.ESTADO_COMPLETADA
        ).select_related('evaluacion__checklist')
        
        # Check if GAES has evaluations
        if items.exists():
            total_items = items.values('evaluacion_id').distinct().count()
            aprendices_count = g.aprendices.count()
            g.estado = "Evaluado" if total_items >= aprendices_count else "Parcial"
        else:
            g.estado = "No evaluado"
    
    return render(request, 'evaluacion/detalle_ficha_evaluacion.html', {
        'ficha': ficha,
        'gaes_list': gaes_list,
        'jurados_ficha': jurados_ficha,
    })


@login_required
def generar_reporte_ficha(request, ficha_id):
    ficha = get_object_or_404(Ficha, id=ficha_id)
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden()
    
    if request.user.rol == 'jurado':
        has_access = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            ficha=ficha,
            estado=Invitacion.ESTADO_ACEPTADA
        ).exists()
        if not has_access:
            return HttpResponseForbidden("No tienes acceso a esta ficha")
    elif request.user.rol == 'instructor':
        has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
        if not has_access:
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                ficha_id=ficha_id,
                estado=Invitacion.ESTADO_ACEPTADA
            ).exists()
        if not has_access:
            has_access = Aprendiz.objects.filter(ficha_id=ficha_id, propietario=request.user).exists()
        if not has_access:
            return HttpResponseForbidden("No tienes acceso a esta ficha")
    
    gaes_list = GAES.objects.filter(ficha=ficha).prefetch_related(
        'aprendices', 'aprendices__resultados'
    ).distinct()
    
    jurados_ficha = Usuario.objects.filter(
        evaluaciones_realizadas__aprendiz__gaes__ficha=ficha
    ).distinct()
    
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    logo_path = settings.BASE_DIR / 'static' / 'images' / 'Logotipo_SENA.png'
    if logo_path.exists():
        c.drawImage(str(logo_path), 0.5 * inch, height - 0.95 * inch, width=0.6 * inch, height=0.6 * inch, preserveAspectRatio=True)

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(width / 2, height - 0.75 * inch, "Reporte de Evaluación por Ficha")
    c.setFont('Helvetica', 10)
    c.drawCentredString(width / 2, height - 0.95 * inch, "SENA - Servicio Nacional de Aprendizaje")
    c.line(0.5 * inch, height - 1.05 * inch, width - 0.5 * inch, height - 1.05 * inch)
    
    y = height - 1.3 * inch
    
    # Ficha info
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.5 * inch, y, f"Ficha: {ficha.numero}")
    y -= 0.2 * inch
    c.setFont('Helvetica', 11)
    c.drawString(0.6 * inch, y, f"Programa: {ficha.programa or '—'}")
    y -= 0.18 * inch
    c.drawString(0.6 * inch, y, f"Instructor: {ficha.instructor.get_full_name() or ficha.instructor.username or '—'}")
    y -= 0.3 * inch
    
    # Jurados
    c.setFont('Helvetica-Bold', 11)
    c.drawString(0.5 * inch, y, "Jurados que evaluaron:")
    y -= 0.18 * inch
    c.setFont('Helvetica', 10)
    for jurado in jurados_ficha:
        c.drawString(0.7 * inch, y, f"• {jurado.get_full_name() or jurado.username}")
        y -= 0.15 * inch
    y -= 0.2 * inch
    
    # GAES con estado
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.5 * inch, y, "GAES y Estado de Evaluación")
    y -= 0.25 * inch
    c.setFont('Helvetica-Bold', 9)
    c.drawString(0.6 * inch, y, "GAES")
    c.drawString(2.5 * inch, y, "Estado")
    c.drawString(3.5 * inch, y, "Fecha")
    y -= 0.15 * inch
    c.line(0.5 * inch, y, width - 0.5 * inch, y)
    y -= 0.08 * inch
    c.setFont('Helvetica', 9)
    
    for g in gaes_list:
        if y < 0.8 * inch:
            c.showPage()
            y = height - 0.75 * inch
            c.setFont('Helvetica', 9)
        c.drawString(0.6 * inch, y, g.nombre)
        
        evaluaciones_gaes = Evaluacion.objects.filter(
            aprendiz__gaes=g
        ).select_related('juror')
        
        if evaluaciones_gaes.filter(estado=Evaluacion.ESTADO_COMPLETADA).exists():
            estado = "Evaluado"
        elif evaluaciones_gaes.exists():
            estado = "Pendiente"
        else:
            estado = "No evaluado"
        
        ultima_eval = evaluaciones_gaes.order_by('-fecha').first()
        fecha_str = ultima_eval.fecha.strftime('%d/%m/%Y') if ultima_eval and ultima_eval.fecha else '—'
        
        c.drawString(2.5 * inch, y, estado)
        c.drawString(3.5 * inch, y, fecha_str)
        y -= 0.15 * inch
    
    c.save()
    buf.seek(0)
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_ficha_{ficha.numero}.pdf"'
    return response


@login_required
def eliminar_evaluacion(request, evaluacion_id):
    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No tienes permiso'}, status=403)
        return HttpResponseForbidden()
    
    aprendiz = evaluacion.aprendiz
    ficha = aprendiz.ficha
    gaes = aprendiz.gaes
    ficha_id = ficha.id if ficha else (gaes.ficha.id if gaes and gaes.ficha else None)
    
    if request.user.rol == 'jurado':
        has_access = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            ficha_id=ficha_id,
            estado=Invitacion.ESTADO_ACEPTADA
        ).exists() if ficha_id else False
        if not has_access:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tienes acceso a esta evaluación'}, status=403)
            return HttpResponseForbidden()
    elif request.user.rol == 'instructor':
        has_access = False
        if ficha_id:
            has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
            if not has_access:
                has_access = Invitacion.objects.filter(
                    Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                    ficha_id=ficha_id,
                    estado=Invitacion.ESTADO_ACEPTADA
                ).exists()
            if not has_access:
                has_access = Aprendiz.objects.filter(id=aprendiz.id, propietario=request.user).exists()
        if not has_access:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tienes acceso a esta evaluación'}, status=403)
            return HttpResponseForbidden()
    
    evaluacion.estado = Evaluacion.ESTADO_CANCELADA
    evaluacion.save(update_fields=['estado'])
    
    resultado = Resultado.objects.filter(aprendiz=aprendiz).first()
    if resultado:
        resultado.calcular_resultado()
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Evaluación archivada.'})
    messages.success(request, 'Evaluación archivada.')
    return redirect('lista_evaluaciones')

@login_required
def lista_resultados(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor', 'aprendiz']:
        return HttpResponseForbidden()
    
    if request.user.rol == 'aprendiz':
        try:
            aprendiz = Aprendiz.objects.get(usuario=request.user)
            resultados = Resultado.objects.filter(aprendiz=aprendiz).select_related('aprendiz').distinct().order_by('-fecha_cierre')
        except Aprendiz.DoesNotExist:
            resultados = Resultado.objects.none()
    elif request.user.rol == 'jurado':
        ficha_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        resultados = Resultado.objects.filter(
            Q(aprendiz__ficha_id__in=ficha_ids) | Q(aprendiz__gaes__ficha_id__in=ficha_ids)
        ).select_related('aprendiz').distinct()
    elif request.user.rol == 'instructor':
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
        resultados = Resultado.objects.filter(
            Q(aprendiz__ficha_id__in=mis_fichas_ids) | Q(aprendiz__gaes__ficha_id__in=mis_fichas_ids)
        ).select_related('aprendiz').distinct()
    else:
        resultados = Resultado.objects.all().select_related('aprendiz').order_by('-fecha_cierre')
    
    # Filtros multicriterio
    filtro_aprendiz = request.GET.get('filtro_aprendiz', '')
    filtro_calificacion = request.GET.get('filtro_calificacion', '')
    filtro_programa = request.GET.get('filtro_programa', '')
    search = request.GET.get('search', '')
    
    if search:
        resultados = resultados.filter(
            Q(aprendiz__nombres__icontains=search) |
            Q(aprendiz__apellidos__icontains=search) |
            Q(aprendiz__documento__icontains=search)
        )
    if filtro_aprendiz:
        resultados = resultados.filter(
            Q(aprendiz__nombres__icontains=filtro_aprendiz) |
            Q(aprendiz__apellidos__icontains=filtro_aprendiz)
        )
    if filtro_calificacion:
        if filtro_calificacion == 'aprobado':
            resultados = resultados.filter(promedio__gte=9)
        elif filtro_calificacion == 'reprobado':
            resultados = resultados.filter(promedio__lt=7)
    if filtro_programa:
        resultados = resultados.filter(aprendiz__programa__icontains=filtro_programa)
    
    return render(request, 'evaluacion/lista_resultados.html', {
        'resultados': resultados,
        'filtro_aprendiz': filtro_aprendiz,
        'filtro_calificacion': filtro_calificacion,
        'filtro_programa': filtro_programa,
        'search': search,
    })


@login_required
def eliminar_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No tienes permiso'}, status=403)
        return HttpResponseForbidden()
    
    aprendiz = resultado.aprendiz
    ficha = aprendiz.ficha
    gaes = aprendiz.gaes
    ficha_id = ficha.id if ficha else (gaes.ficha.id if gaes and gaes.ficha else None)
    
    if request.user.rol == 'jurado':
        has_access = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            ficha_id=ficha_id,
            estado=Invitacion.ESTADO_ACEPTADA
        ).exists() if ficha_id else False
        if not has_access:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tienes acceso a este resultado'}, status=403)
            return HttpResponseForbidden()
    elif request.user.rol == 'instructor':
        has_access = False
        if ficha_id:
            has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
            if not has_access:
                has_access = Invitacion.objects.filter(
                    Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                    ficha_id=ficha_id,
                    estado=Invitacion.ESTADO_ACEPTADA
                ).exists()
            if not has_access:
                has_access = Aprendiz.objects.filter(id=aprendiz.id, propietario=request.user).exists()
        if not has_access:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tienes acceso a este resultado'}, status=403)
            return HttpResponseForbidden()
    
    aprendiz = resultado.aprendiz
    evaluaciones_archivar = Evaluacion.objects.filter(aprendiz=aprendiz)
    evaluaciones_archivar.update(estado=Evaluacion.ESTADO_CANCELADA)
    
    resultado.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Resultado eliminado.'})
    messages.success(request, 'Resultado eliminado.')
    return redirect('lista_resultados')

@login_required
def ver_resultado(request, resultado_id):
    resultado = get_object_or_404(Resultado, id=resultado_id)
    if request.user.rol not in ['administrador', 'jurado', 'instructor', 'aprendiz']:
        return HttpResponseForbidden()
    
    aprendiz = resultado.aprendiz
    ficha = aprendiz.ficha
    gaes = aprendiz.gaes
    ficha_id = ficha.id if ficha else (gaes.ficha.id if gaes and gaes.ficha else None)
    
    if request.user.rol == 'jurado':
        has_access = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            ficha_id=ficha_id,
            estado=Invitacion.ESTADO_ACEPTADA
        ).exists() if ficha_id else False
        if not has_access:
            return HttpResponseForbidden('No tienes acceso a este resultado')
    elif request.user.rol == 'instructor':
        has_access = False
        if ficha_id:
            has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
            if not has_access:
                has_access = Invitacion.objects.filter(
                    Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                    ficha_id=ficha_id,
                    estado=Invitacion.ESTADO_ACEPTADA
                ).exists()
            if not has_access:
                has_access = Aprendiz.objects.filter(id=aprendiz.id, propietario=request.user).exists()
        if not has_access:
            return HttpResponseForbidden('No tienes acceso a este resultado')
    
    aprendiz = resultado.aprendiz
    evaluaciones = Evaluacion.objects.filter(
        aprendiz=aprendiz
    ).select_related('checklist', 'juror').prefetch_related('items__item').order_by('-fecha').distinct()
    for e in evaluaciones:
        e.ordered_items = list(e.items.all().order_by('item__orden'))
    return render(request, 'evaluacion/ver_resultado.html', {
        'resultado': resultado,
        'evaluaciones': evaluaciones,
        'aprendiz': aprendiz,
    })

@login_required
def generar_reporte_pdf(request, resultado_id):
    if request.user.rol not in ['administrador', 'jefe', 'instructor', 'jurado', 'aprendiz']:
        return HttpResponseForbidden()
    
    resultado = get_object_or_404(Resultado.objects.select_related('aprendiz__ficha', 'aprendiz__gaes'), id=resultado_id)
    aprendiz = resultado.aprendiz
    
    if request.user.rol == 'aprendiz':
        if aprendiz.usuario != request.user:
            return HttpResponseForbidden()
        ficha = aprendiz.ficha
        ficha_id = ficha.id if ficha else None
    else:
        ficha = aprendiz.ficha
        gaes_ficha = aprendiz.gaes.ficha if aprendiz.gaes else None
        ficha_id = ficha.id if ficha else (gaes_ficha.id if gaes_ficha else None)
        
        if request.user.rol == 'jurado':
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                ficha_id=ficha_id,
                estado=Invitacion.ESTADO_ACEPTADA
            ).exists() if ficha_id else False
            if not has_access:
                return HttpResponseForbidden()
        elif request.user.rol == 'instructor':
            has_access = False
            if ficha_id:
                has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
                if not has_access:
                    has_access = Invitacion.objects.filter(
                        Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                        ficha_id=ficha_id,
                        estado=Invitacion.ESTADO_ACEPTADA
                    ).exists()
                if not has_access:
                    has_access = Aprendiz.objects.filter(id=aprendiz.id, propietario=request.user).exists()
            if not has_access:
                return HttpResponseForbidden()

    # Generate PDF for both GET and POST
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    logo_path = settings.BASE_DIR / 'static' / 'images' / 'Logotipo_SENA.png'
    if logo_path.exists():
        c.drawImage(str(logo_path), 0.5 * inch, height - 0.95 * inch, width=0.6 * inch, height=0.6 * inch, preserveAspectRatio=True)

    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(width / 2, height - 0.75 * inch, "Reporte de Resultado de Evaluación")
    c.setFont('Helvetica', 10)
    c.drawCentredString(width / 2, height - 0.95 * inch, "Sistema de Gestión de Sustentaciones SENA")
    c.line(0.5 * inch, height - 1.05 * inch, width - 0.5 * inch, height - 1.05 * inch)

    y = height - 1.3 * inch

    # Learner info
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.5 * inch, y, "Información del Aprendiz")
    y -= 0.25 * inch
    c.setFont('Helvetica', 11)
    aprend = resultado.aprendiz
    c.drawString(0.6 * inch, y, f"Documento: {getattr(aprend, 'documento', '')}")
    y -= 0.18 * inch
    c.drawString(0.6 * inch, y, f"Nombres: {getattr(aprend, 'nombres', '')}")
    y -= 0.18 * inch
    c.drawString(0.6 * inch, y, f"Apellidos: {getattr(aprend, 'apellidos', '')}")
    y -= 0.18 * inch
    c.drawString(0.6 * inch, y, f"Programa: {getattr(aprend, 'programa', '')}")
    y -= 0.18 * inch
    ficha_obj = aprend.ficha if aprend.ficha_id else None
    c.drawString(0.6 * inch, y, f"Ficha: {ficha_obj.numero if ficha_obj else ''}")
    y -= 0.3 * inch

    # Evaluation info
    c.setFont('Helvetica-Bold', 12)
    c.drawString(0.5 * inch, y, "Resultado de la Evaluación")
    y -= 0.25 * inch
    c.setFont('Helvetica', 11)
    c.drawString(0.6 * inch, y, f"Calificación Final: {resultado.calificacion_final}")
    y -= 0.18 * inch
    c.drawString(0.6 * inch, y, f"Fecha de Cierre: {resultado.fecha_cierre.strftime('%d/%m/%Y %H:%M') if resultado.fecha_cierre else ''}")
    y -= 0.18 * inch
    if resultado.observaciones_generales:
        c.drawString(0.6 * inch, y, f"Observaciones Generales: {resultado.observaciones_generales}")
        y -= 0.25 * inch

    # Get latest completed evaluacion for this aprendiz
    evals = Evaluacion.objects.filter(aprendiz=aprend, estado=Evaluacion.ESTADO_COMPLETADA).order_by('-fecha')
    if evals.exists():
        evaluacion = evals.first()
        c.setFont('Helvetica-Bold', 12)
        c.drawString(0.5 * inch, y, "Detalle por Criterio (Última Evaluación Completada)")
        y -= 0.25 * inch
        # Table header
        c.setFont('Helvetica-Bold', 9)
        c.drawString(0.6 * inch, y, "Criterio")
        c.drawString(3.5 * inch, y, "✓ Cumple")
        c.drawString(4.5 * inch, y, "Observaciones")
        y -= 0.18 * inch
        c.line(0.5 * inch, y, width - 0.5 * inch, y)
        y -= 0.08 * inch
        c.setFont('Helvetica', 8)
        for item_evaluacion in evaluacion.items.select_related('item').order_by('item__orden'):
            if y < 0.8 * inch:
                c.showPage()
                y = height - 0.75 * inch
                c.setFont('Helvetica', 8)
            criterio_text = item_evaluacion.item.criterio if item_evaluacion.item else ''
            # Truncate if too long
            if len(criterio_text) > 40:
                criterio_text = criterio_text[:37] + '...'
            c.drawString(0.6 * inch, y, criterio_text)
            cumple = "✓ Sí" if item_evaluacion.puntaje > 0 else "✗ No"
            c.drawString(3.5 * inch, y, cumple)
            obs = item_evaluacion.observaciones
            if obs:
                if len(obs) > 50:
                    obs = obs[:47] + '...'
                c.drawString(4.5 * inch, y, obs)
            y -= 0.15 * inch
        y -= 0.2 * inch

    # Footer
    c.setFont('Helvetica-Oblique', 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width / 2, 0.5 * inch, f"Generado por Sistema de Gestión de Sustentaciones SENA - {timezone.now().strftime('%d/%m/%Y %H:%M')}")
    c.showPage()
    c.save()

    buf.seek(0)
    filename = f'resultado_{resultado.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    response = HttpResponse(buf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def exportar_resultados_excel(request):
    if request.user.rol not in ['administrador', 'jefe']:
        return HttpResponseForbidden()
    resultados = Resultado.objects.all().select_related('aprendiz').order_by('-fecha_cierre')
    from django.http import HttpResponse
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Aprendiz', 'Promedio', 'Calificacion Final', 'Fecha'])
    for r in resultados:
        writer.writerow([
            r.id, r.aprendiz.nombres if r.aprendiz else '', r.promedio, r.calificacion_final, r.fecha_cierre,
        ])
    out_value = output.getvalue()
    response = HttpResponse(out_value, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=resultados.csv'
    return response

@login_required
def consumir_api_estadisticas(request):
    from django.http import JsonResponse
    if request.user.rol not in ['administrador', 'jefe']:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    stats = {
        'aprendices': Aprendiz.objects.count(),
        'evaluaciones': Evaluacion.objects.count(),
        'resultados': Resultado.objects.count(),
        'pendientes': Evaluacion.objects.filter(estado='pendiente').count(),
        'completadas': Evaluacion.objects.filter(estado='completada').count(),
    }
    return JsonResponse(stats)

@login_required
def api_estadisticas_basicas(request):
    from django.http import JsonResponse
    if request.user.rol not in ['administrador', 'jefe']:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    data = {
        'total_aprendices': Aprendiz.objects.count(),
        'total_evaluaciones': Evaluacion.objects.count(),
        'total_resultados': Resultado.objects.count(),
    }
    return JsonResponse(data)

@login_required
def api_chart_gaes(request):
    from django.http import JsonResponse
    from django.db.models import Count
    qs = GAES.objects.annotate(cant=Count('aprendices', distinct=True)).filter(cant__gt=0)
    data = {
        'labels': [g.nombre for g in qs],
        'values': [g.cant for g in qs],
    }
    return JsonResponse(data)


@login_required
def api_checklist_items(request, checklist_id):
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    if request.user.rol != 'administrador' and checklist.propietario != request.user:
        return JsonResponse({'error': 'No tienes acceso'}, status=403)
    items = list(checklist.items.order_by('orden').values('id', 'criterio', 'descripcion', 'orden'))
    return JsonResponse({'items': items})


@login_required
def evaluar_gaes(request, gaes_id):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    gaes = get_object_or_404(GAES, pk=gaes_id)
    ficha = gaes.ficha
    ficha_id = ficha.id if ficha else None
    
    if request.user.rol == 'jurado':
        has_access = False
        if ficha_id:
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                ficha_id=ficha_id,
                estado=Invitacion.ESTADO_ACEPTADA
            ).exists()
        if not has_access:
            return HttpResponseForbidden()
    elif request.user.rol == 'instructor':
        has_access = False
        if ficha_id:
            has_access = Ficha.objects.filter(id=ficha_id, instructor=request.user).exists()
            if not has_access:
                has_access = Invitacion.objects.filter(
                    Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                    ficha_id=ficha_id,
                    estado=Invitacion.ESTADO_ACEPTADA
                ).exists()
            if not has_access:
                has_access = Aprendiz.objects.filter(gaes=gaes, propietario=request.user).exists()
        if not has_access:
            return HttpResponseForbidden()
    checklist = None
    items = []
    creadas = 0
    if request.method == 'POST':
        checklist_id = request.POST.get('checklist_id')
        if not checklist_id:
            messages.error(request, 'Selecciona un checklist')
            return redirect('evaluar_gaes', gaes_id=gaes_id)
        checklist = get_object_or_404(Checklist, pk=checklist_id, activo=True)
        # Permitir acceso si: es administrador, o el propietario es el usuario, o viene de una invitación aceptada
        has_access = request.user.rol == 'administrador' or checklist.propietario == request.user
        if not has_access and request.user.rol == 'jurado':
            has_access = Invitacion.objects.filter(
                Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                estado=Invitacion.ESTADO_ACEPTADA,
                checklist_id=checklist_id
            ).exists()
        if not has_access:
            return HttpResponseForbidden('No tienes acceso a este checklist')
        items = checklist.items.order_by('orden')
        puntajes = {}
        for item in items:
            puntajes[item.id] = {
                'puntaje': int(request.POST.get(f'puntaje_{item.id}', '0') or '0'),
                'observaciones': request.POST.get(f'observaciones_{item.id}', ''),
            }
        aprendiz_ids = request.POST.getlist('aprendiz_ids')
        if not aprendiz_ids:
            messages.error(request, 'No hay aprendices para evaluar en este GAES')
            return redirect('evaluar_gaes', gaes_id=gaes_id)
        creadas = 0
        for aid in aprendiz_ids:
            aprendiz = get_object_or_404(Aprendiz, id=aid)
            evaluacion, _ = Evaluacion.objects.get_or_create(
                aprendiz=aprendiz,
                checklist=checklist,
                defaults={'juror': request.user, 'estado': Evaluacion.ESTADO_PENDIENTE}
            )
            for item in items:
                EvaluacionItem.objects.update_or_create(
                    evaluacion=evaluacion, item=item,
                    defaults={'puntaje': puntajes[item.id]['puntaje'], 'observaciones': puntajes[item.id]['observaciones']}
                )
            evaluacion.calcular_puntaje()
            evaluacion.estado = Evaluacion.ESTADO_COMPLETADA
            evaluacion.save(update_fields=['calificacion_total', 'estado'])
            ev_items = EvaluacionItem.objects.filter(evaluacion=evaluacion)
            total = ev_items.count()
            aprobados = ev_items.filter(puntaje__gt=0).count()
            resultado, _ = Resultado.objects.get_or_create(aprendiz=aprendiz)
            if total > 0 and aprobados == total:
                resultado.calificacion_final = 'Cumplió'
                resultado.promedio = 100
            else:
                resultado.calificacion_final = 'No cumplió'
                resultado.promedio = ev_items.aggregate(total=Sum('puntaje'))['total'] or 0
            resultado.save()
            creadas += 1
        messages.success(request, f'Evaluación completada para {creadas} aprendices de {gaes.nombre}')
        return redirect('jurado_evaluaciones_gaes', gaes_id=gaes_id)
    else:
        checklist_id = request.GET.get('checklist_id')
        if checklist_id:
            checklist = get_object_or_404(Checklist, pk=checklist_id, activo=True)
            # Permitir acceso si: es administrador, o el propietario es el usuario, o viene de una invitación aceptada
            has_access = request.user.rol == 'administrador' or checklist.propietario == request.user
            if not has_access and request.user.rol == 'jurado':
                has_access = Invitacion.objects.filter(
                    Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
                    estado=Invitacion.ESTADO_ACEPTADA,
                    checklist_id=checklist_id
                ).exists()
            if not has_access:
                return HttpResponseForbidden('No tienes acceso a este checklist')
            items = checklist.items.order_by('orden')
    
    if request.user.rol == 'administrador':
        checklists = Checklist.objects.filter(activo=True)
    elif request.user.rol == 'instructor':
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas_ids)
        propietario_fichas = Aprendiz.objects.filter(propietario=request.user).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
        checklists = Checklist.objects.filter(
            activo=True
        ).filter(
            Q(propietario=request.user) |
            Q(items__competencia__ficha_id__in=mis_fichas_ids)
        ).distinct()
    elif request.user.rol == 'jurado':
        ficha_ids = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        
        # Also get checklists directly from invitations
        inv_checklists = Invitacion.objects.filter(
            Q(instructores_jurados=request.user) | Q(instructor_invitado=request.user),
            estado=Invitacion.ESTADO_ACEPTADA,
            checklist__isnull=False
        ).values_list('checklist_id', flat=True).distinct()
        
        checklists = Checklist.objects.filter(
            models.Q(id__in=inv_checklists) |
            models.Q(items__competencia__ficha_id__in=ficha_ids),
            activo=True
        ).distinct()
    else:
        checklists = Checklist.objects.none()
    
    aprendices = Aprendiz.objects.filter(gaes=gaes).select_related('usuario', 'fase', 'ficha').order_by('nombres', 'apellidos')
    return render(request, 'evaluacion/evaluar_gaes.html', {
        'gaes': gaes,
        'aprendices': aprendices,
        'checklists': checklists,
        'checklist': checklist,
        'items': items,
    })


def generar_pdf_gaes_evaluacion(request, gaes_id, checklist_id):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    gaes = get_object_or_404(GAES, pk=gaes_id)
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    aprendiz_id = request.GET.get('aprendiz_id')
    if aprendiz_id:
        aprendices = Aprendiz.objects.filter(id=aprendiz_id, gaes=gaes).select_related('usuario', 'fase', 'ficha').order_by('nombres', 'apellidos')
    else:
        aprendices = Aprendiz.objects.filter(gaes=gaes).select_related('usuario', 'fase', 'ficha').order_by('nombres', 'apellidos')
    items = checklist.items.order_by('orden')

    if not aprendices:
        messages.error(request, 'No hay aprendices en este GAES para generar PDF')
        return redirect('evaluar_gaes', gaes_id=gaes_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=48, leftMargin=48,
                            topMargin=48, bottomMargin=48)

    styles = getSampleStyleSheet()

    story = []
    
    logo_path = settings.BASE_DIR / 'static' / 'images' / 'Logotipo_SENA.png'
    if logo_path.exists():
        img = Image(str(logo_path), width=80, height=40)
        story.append(img)
        story.append(Spacer(1, 12))
    
    story.append(Paragraph(f"Evaluación GAES: {gaes.nombre}", styles['Title']))
    story.append(Paragraph(f"Checklist: {checklist.titulo}", styles['Normal']))
    story.append(Paragraph(f"Fecha: {timezone.now().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 12))

    for aprendiz in aprendices:
        try:
            evaluacion = Evaluacion.objects.get(aprendiz=aprendiz, checklist=checklist)
        except Evaluacion.DoesNotExist:
            evaluacion = None
        ev_items = EvaluacionItem.objects.filter(evaluacion=evaluacion).select_related('item') if evaluacion else []

        story.append(Paragraph(f"Aprendiz: {aprendiz.nombres} {aprendiz.apellidos} (Doc: {aprendiz.documento})", styles['Heading3']))

        if ev_items:
            tabla_datos = [['#', 'Criterio', 'CUMPLE (SI)', 'NO CUMPLE (NO)', 'Observaciones']]
            for ev_item in ev_items:
                estado = 'X' if ev_item.puntaje > 0 else ''
                estado_no = 'X' if ev_item.puntaje == 0 else ''
                tabla_datos.append([
                    str(ev_item.item.orden),
                    Paragraph(str(ev_item.item.criterio)[:80], styles['Normal']),
                    estado,
                    estado_no,
                    Paragraph(str(ev_item.observaciones or '')[:60], styles['Normal']),
                ])
        else:
            tabla_datos = [['#', 'Criterio', 'CUMPLE (SI)', 'NO CUMPLE (NO)', 'Observaciones']]
            for item in items:
                tabla_datos.append([
                    str(item.orden),
                    Paragraph(str(item.criterio)[:80], styles['Normal']),
                    '',
                    '',
                    '',
                ])

        tabla = Table(tabla_datos, colWidths=[30, 210, 55, 65, 130])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f3f4f6')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="evaluacion_gaes_{gaes.id}.pdf"'
    return response
