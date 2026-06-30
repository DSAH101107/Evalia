# apps/jurados/views.py
"""
Vistas del módulo de Jurado.
El jurado:
  - Ve su dashboard con invitaciones pendientes y evaluaciones realizadas
  - Consulta la ficha asignada
  - Consulta lista de chequeo
  - Ve sus resultados y evaluaciones
  - Imprime reporte PDF de sus evaluaciones
  - Ve el historial de evaluaciones realizadas
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.conf import settings

from apps.usuarios.models import Usuario
from apps.evaluacion.models import (
    Aprendiz, Evaluacion, EvaluacionItem,
    Resultado, Invitacion, Checklist, ChecklistItem,
    Fase, Competencia, GAES, Ficha,
)
from apps.auditoria.models import LogAuditoria
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jurados_relacionados(user):
    """Devuelve los IDs de jurados para usar en consultas de dashboards compartidos."""
    return Usuario.objects.filter(rol='jurado').values_list('id', flat=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard del Jurado
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso a esta sección')

    # Invitaciones recibidas por este usuario
    invitaciones_recibidas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user)
    )
    invitaciones_pendientes = invitaciones_recibidas.filter(
        estado=Invitacion.ESTADO_PENDIENTE,
    )
    invitacion_aceptada = invitaciones_recibidas.filter(
        estado=Invitacion.ESTADO_ACEPTADA,
    ).first()

    # Aceptar invitación automáticamente al acceder al dashboard si hay una pendiente
    # (no se fuerza; solo se muestra)
    # Evaluaciones realizadas por este jurado
    evaluaciones = Evaluacion.objects.filter(
        juror=request.user
    ).select_related('aprendiz', 'checklist').order_by('-fecha')

    total_evaluaciones = evaluaciones.count()
    evaluaciones_completadas = evaluaciones.filter(
        estado=Evaluacion.ESTADO_COMPLETADA
    ).count()
    evaluaciones_pendientes = total_evaluaciones - evaluaciones_completadas

    # Resultados asociados a las evaluaciones de este jurado
    evaluados_ids = evaluaciones.values_list('aprendiz_id', flat=True).distinct()
    resultados = Resultado.objects.filter(
        aprendiz_id__in=evaluados_ids
    ).select_related('aprendiz').order_by('-fecha_cierre')

    # Invitaciones enviadas por este jurado
    mis_invitaciones = Invitacion.objects.filter(instructor=request.user)

    # Ficha asignada (la ficha del primer aprendiz evaluado por el jurado)
    ficha_asignada = None
    primera_eval = evaluaciones.select_related('aprendiz__ficha').first()
    if primera_eval and primera_eval.aprendiz.ficha:
        ficha_asignada = primera_eval.aprendiz.ficha

    # GAES disponibles para este jurado (incluye fichas del instructor principal + propietario + invitaciones)
    ficha_ids = Evaluacion.objects.filter(
        juror=request.user
    ).values_list('aprendiz__ficha_id', flat=True).distinct()
    inv_fichas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    ficha_asignada_ids = Ficha.objects.filter(
        instructor=request.user
    ).values_list('id', flat=True).distinct()
    ficha_ids = set(ficha_ids) | set(inv_fichas) | set(ficha_asignada_ids)
    
    # También incluir fichas donde es propietario de los aprendices
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    ficha_ids |= set(propietario_fichas)
    
    # Check if any aprendices exist in assigned fichas
    if ficha_ids:
        gaes_a_evaluar = GAES.objects.filter(
            models.Q(fichas__id__in=ficha_ids) |
            models.Q(aprendices__ficha__id__in=ficha_ids) |
            models.Q(aprendices__gaes__ficha__id__in=ficha_ids)
        ).annotate(
            aprendices_count=Count('aprendices', distinct=True)
        ).filter(aprendices_count__gt=0).distinct().order_by('nombre')
    else:
        # Si el jurado no tiene fichas asignadas, no mostrar GAES
        gaes_a_evaluar = GAES.objects.none()

    # ── Datos para gráficas ────────────────────────────────────────────────
    if request.user.rol == 'jurado' and ficha_ids:
        gaes_qs = (GAES.objects
                   .filter(fichas__id__in=ficha_ids)
                   .annotate(cant=Count('aprendices', distinct=True))
                   .filter(cant__gt=0).order_by('nombre'))
        ficha_qs = (Ficha.objects
                    .filter(id__in=ficha_ids)
                    .annotate(cant=Count('aprendices', distinct=True))
                    .filter(cant__gt=0)
                    .order_by('numero'))
        _mis_fases_ids = (Aprendiz.objects
                          .filter(models.Q(ficha__id__in=ficha_ids) | models.Q(gaes__ficha__id__in=ficha_ids))
                          .filter(fase__isnull=False)
                          .values_list('fase_id', flat=True)
                          .distinct())
        fase_qs = (Fase.objects
                   .filter(id__in=_mis_fases_ids)
                   .annotate(cant=Count('aprendices', distinct=True))
                   .filter(cant__gt=0)
                   .order_by('numero'))
    else:
        gaes_qs = GAES.objects.none()
        ficha_qs = Ficha.objects.none()
        fase_qs = Fase.objects.none()
    gaes_labels = [g.nombre for g in gaes_qs]
    gaes_values = [g.cant for g in gaes_qs]
    ficha_labels = [f.numero for f in ficha_qs]
    ficha_values = [f.cant for f in ficha_qs]
    fase_labels = [f'Fase {f.numero}' for f in fase_qs]
    fase_values = [f.cant for f in fase_qs]

    return render(request, 'usuarios/dashboard_jurado.html', {
        'invitaciones_pendientes': invitaciones_pendientes,
        'invitacion_aceptada': invitacion_aceptada,
        'evaluaciones': evaluaciones,
        'total_evaluaciones': total_evaluaciones,
        'evaluaciones_completadas': evaluaciones_completadas,
        'evaluaciones_pendientes': evaluaciones_pendientes,
        'resultados': resultados,
        'mis_invitaciones': mis_invitaciones,
        'ficha_asignada': ficha_asignada,
        'gaes_labels': gaes_labels,
        'gaes_values': gaes_values,
        'ficha_labels': ficha_labels,
        'ficha_values': ficha_values,
        'fase_labels': fase_labels,
        'fase_values': fase_values,
        'gaes_a_evaluar': gaes_a_evaluar,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Ficha Asignada
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mi_ficha(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')

    # La ficha asignada se deduce de las evaluaciones del jurado
    # TAMBIÉN incluye fichas donde el usuario es instructor principal o es propietario
    ficha_ids = set(Evaluacion.objects.filter(
        juror=request.user
    ).values_list('aprendiz__ficha_id', flat=True).distinct())
    
    inv_fichas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    ficha_ids |= set(inv_fichas)
    
    ficha_asignada_ids = Ficha.objects.filter(
        instructor=request.user
    ).values_list('id', flat=True).distinct()
    ficha_ids |= set(ficha_asignada_ids)
    
    # También incluir fichas donde es propietario
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    ficha_ids |= set(propietario_fichas)

    fichas = Ficha.objects.filter(id__in=ficha_ids).select_related(
        'gaes', 'trimestre', 'instructor'
    ).prefetch_related('aprendices')

    return render(request, 'fichas/lista_fichas.html', {
        'fichas': fichas,
        'filtro': '',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Lista de GAES (Jurado)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def jurado_gaes(request):
    """Muestra los GAES con aprendices para el jurado evaluar."""
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')
    
    # Fichas del jurado (invitaciones aceptadas)
    ficha_ids = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    
    # GAES con aprendices en esas fichas o con aprendices que tienen GAES asignado
    gaes = GAES.objects.filter(
        models.Q(fichas__id__in=ficha_ids) |
        models.Q(aprendices__gaes__ficha__id__in=ficha_ids)
    ).annotate(
        aprendices_count=Count('aprendices', distinct=True)
    ).filter(aprendices_count__gt=0).distinct().order_by('nombre')
    
    return render(request, 'jurados/lista_gaes.html', {
        'gaes_list': gaes,
    })

# ─────────────────────────────────────────────────────────────────────────────
# Lista de Chequeo (Jurado)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mi_checklist(request, checklist_id=None):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')

    # Checklists permitidos: de la ficha del jurado (incluye fichas del instructor principal)
    mis_fichas_ids = Ficha.objects.filter(
        instructor=request.user
    ).values_list('id', flat=True).distinct()
    
    # TAMBIÉN incluir fichas de aprendices donde el usuario es propietario
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids = set(mis_fichas_ids) | set(propietario_fichas)
    
    inv_fichas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(inv_fichas)
    
    eval_fichas = Evaluacion.objects.filter(
        juror=request.user
    ).values_list('aprendiz__ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(eval_fichas)
    
    mis_fichas_ids = list(mis_fichas_ids)

    checklists = Checklist.objects.filter(activo=True)
    if mis_fichas_ids:
        checklists = checklists.filter(
            items__competencia__ficha_id__in=mis_fichas_ids
        ).distinct()
    else:
        checklists = Checklist.objects.none()

    checklist = None
    items = []
    if checklist_id:
        checklist = get_object_or_404(Checklist, id=checklist_id, activo=True)
        if not checklists.filter(id=checklist.id).exists():
            return HttpResponseForbidden('No tienes acceso a este checklist')
        items = ChecklistItem.objects.filter(
            checklist=checklist
        ).select_related('competencia').order_by('orden')

    return render(request, 'jurados/mi_checklist.html', {
        'checklists': checklists,
        'checklist': checklist,
        'items': items,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Resultados del Jurado
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mis_resultados(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')

    resultados = Resultado.objects.filter(
        aprendiz__evaluaciones__juror=request.user
    ).select_related('aprendiz__ficha', 'aprendiz__gaes').distinct().order_by('-fecha_cierre')

    # Búsqueda simple
    search = request.GET.get('search', '')
    if search:
        resultados = resultados.filter(
            Q(aprendiz__nombres__icontains=search) |
            Q(aprendiz__apellidos__icontains=search) |
            Q(aprendiz__documento__icontains=search)
        )

    return render(request, 'jurados/mis_resultados.html', {
        'resultados': resultados,
        'search': search,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Historial de evaluaciones del Jurado
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def mis_evaluaciones(request):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')

    evaluaciones = Evaluacion.objects.filter(
        juror=request.user
    ).select_related('aprendiz', 'checklist').order_by('-fecha')

    search = request.GET.get('search', '')
    if search:
        evaluaciones = evaluaciones.filter(
            Q(aprendiz__nombres__icontains=search) |
            Q(aprendiz__apellidos__icontains=search) |
            Q(checklist__titulo__icontains=search)
        )

    return render(request, 'jurados/mis_evaluaciones.html', {
        'evaluaciones': evaluaciones,
        'search': search,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Evaluar por GAES
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def evaluar_gaes(request, gaes_id):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')
    
    gaes = get_object_or_404(GAES, id=gaes_id)
    
    # Get fichas assigned to this jurado (ya calculado arriba)
    # ficha_ids viene del contexto del dashboard
    ficha_ids = set()
    
    inv_fichas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    ficha_ids |= set(inv_fichas)
    
    # Get aprendices del GAES (sin importar si tienen ficha o no)
    aprendices = Aprendiz.objects.filter(gaes=gaes).select_related('ficha', 'gaes', 'fase')
    
    if not aprendices.exists():
        messages.warning(request, 'No hay aprendices en este GAES.')
        return redirect('dashboard_jurado')
    
    # Get checklists: primero de la invitación, luego por competencias de la ficha
    inv_checklists = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA,
        checklist__isnull=False
    ).values_list('checklist_id', flat=True).distinct()
    
    if request.user.rol == 'administrador':
        checklists = Checklist.objects.filter(activo=True)
    elif request.user.rol == 'instructor':
        checklists = Checklist.objects.filter(
            activo=True,
            items__competencia__ficha_id__in=ficha_ids
        ).distinct() if ficha_ids else Checklist.objects.none()
    elif request.user.rol == 'jurado':
        checklists = Checklist.objects.filter(
            models.Q(id__in=inv_checklists),
            activo=True
        ).distinct()
    else:
        checklists = Checklist.objects.none()
    
    if request.method == 'POST':
        checklist_id = request.POST.get('checklist_id')
        if checklist_id:
            checklist = get_object_or_404(Checklist, id=checklist_id, activo=True)
            # Permitir acceso si: es administrador, o el propietario es el usuario, o viene de una invitación aceptada
            has_access = request.user.rol == 'administrador' or checklist.propietario == request.user
            if not has_access and request.user.rol == 'jurado':
                has_access = Invitacion.objects.filter(
                    models.Q(instructores_jurados=request.user) | models.Q(instructor_invitado=request.user),
                    estado=Invitacion.ESTADO_ACEPTADA,
                    checklist_id=checklist_id
                ).exists()
            if not has_access:
                return HttpResponseForbidden('No tienes acceso a este checklist')
            # Crear evaluación para cada aprendiz del GAES
            for aprendiz in aprendices:
                Evaluacion.objects.get_or_create(
                    aprendiz=aprendiz,
                    juror=request.user,
                    checklist=checklist,
                    defaults={'estado': 'pendiente'}
                )
            messages.success(request, f'Se crearon las evaluaciones para {aprendices.count()} aprendices del GAES.')
            return redirect('jurado_evaluaciones_gaes', gaes_id=gaes_id)
        else:
            messages.error(request, 'Debes seleccionar un checklist.')
    
    return render(request, 'jurados/evaluar_gaes.html', {
        'gaes': gaes,
        'aprendices': aprendices,
        'checklists': checklists,
    })


@login_required
def jurado_evaluaciones_gaes(request, gaes_id):
    """Muestra los resultados del GAES para el jurado."""
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')
    
    gaes = get_object_or_404(GAES, id=gaes_id)
    
    # Obtener checklist de la invitación
    checklist_id = None
    inv = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA,
        ficha__gaes=gaes
    ).values_list('checklist_id', flat=True).first()
    
    if inv:
        checklist_id = inv
    
    # Obtener aprendices del GAES con sus resultados
    aprendices = Aprendiz.objects.filter(gaes=gaes).select_related('fase').order_by('nombres', 'apellidos')
    
    aprendices_con_resultado = []
    for aprendiz in aprendices:
        resultado = aprendiz.resultados.first() if hasattr(aprendiz, 'resultados') else None
        aprendices_con_resultado.append({
            'aprendiz': aprendiz,
            'resultado': resultado,
        })
    
    return render(request, 'jurados/evaluaciones_gaes.html', {
        'gaes': gaes,
        'aprendices_con_resultado': aprendices_con_resultado,
        'checklist_id': checklist_id,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Imprimir Reporte PDF de Evaluacion
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def imprimir_reporte(request, evaluacion_id):
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso')

    evaluacion = get_object_or_404(Evaluacion, id=evaluacion_id)
    # El jurado solo puede ver reportes de sus propias evaluaciones
    if evaluacion.juror != request.user and request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta evaluación')

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from io import BytesIO

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        w, h = letter

        def header_pdf():
            logo_path = settings.BASE_DIR / 'static' / 'images' / 'Logotipo_SENA.png'
            if logo_path.exists():
                c.drawImage(str(logo_path), 0.5 * inch, h - 0.95 * inch, width=0.6 * inch, height=0.6 * inch, preserveAspectRatio=True)
            c.setFont('Helvetica-Bold', 13)
            c.drawCentredString(w / 2, h - 0.6 * inch, 'REPORTE DE EVALUACION — SENA')
            c.setFont('Helvetica', 8.5)
            c.drawCentredString(w / 2, h - 0.8 * inch,
                                'Sistema de Gestion de Sustentaciones')
            c.setStrokeColorRGB(0.18, 0.25, 0.34)
            c.setLineWidth(1.5)
            c.line(0.75 * inch, h - 0.9 * inch, w - 0.75 * inch, h - 0.9 * inch)

        header_pdf()
        y = h - 1.15 * inch
        xl = 0.9 * inch
        xv = 3.2 * inch

        def row_pdf(label, value):
            nonlocal y
            if y < 0.85 * inch:
                c.showPage()
                header_pdf()
                y = h - 1.15 * inch
            c.setFont('Helvetica-Bold', 10)
            c.drawString(xl, y, label + ':')
            c.setFont('Helvetica', 10)
            c.drawString(xv, y, str(value)[:100])
            y -= 0.22 * inch

        aprendiz = evaluacion.aprendiz
        row_pdf('Aprendiz', f'{aprendiz.nombres} {aprendiz.apellidos}')
        row_pdf('Documento', str(aprendiz.documento))
        row_pdf('Programa', str(aprendiz.programa or '—'))
        row_pdf('Ficha', str(aprendiz.ficha or '—'))
        row_pdf('GAES', str(aprendiz.gaes or '—'))
        row_pdf('Fase', str(aprendiz.fase or '—'))
        row_pdf('Jurado', str(evaluacion.juror.get_full_name() or evaluacion.juror.username))
        row_pdf('Fecha', evaluacion.fecha.strftime('%d/%m/%Y %H:%M') if evaluacion.fecha else '—')
        row_pdf('Estado', evaluacion.get_estado_display())
        row_pdf('Calificacion total', str(evaluacion.calificacion_total))

        if evaluacion.observaciones:
            y -= 0.1 * inch
            c.setFont('Helvetica-Bold', 10)
            c.drawString(xl, y, 'Observaciones:')
            y -= 0.18 * inch
            c.setFont('Helvetica', 9)
            for line in (evaluacion.observaciones or '').split('\n'):
                if y < 0.85 * inch:
                    c.showPage()
                    header_pdf()
                    y = h - 1.15 * inch
                c.drawString(xv, y, line[:100])
                y -= 0.18 * inch

        # Tabla de items con checkboxes
        items = EvaluacionItem.objects.filter(
            evaluacion=evaluacion
        ).select_related('item')

        if items.exists():
            y -= 0.15 * inch
            c.setFont('Helvetica-Bold', 10)
            c.drawString(xl, y, 'Items evaluados:')
            y -= 0.22 * inch

            col_criterio = 2.8 * inch
            col_checkbox = 0.8 * inch
            col_obs = 2.9 * inch
            row_h = 0.25 * inch

            def tbl_header():
                c.setFillColorRGB(0.29, 0.44, 0.65)
                c.rect(xl, y - 2, col_criterio, row_h - 2, fill=1, stroke=0)
                c.rect(xl + col_criterio, y - 2, col_checkbox, row_h - 2, fill=1, stroke=0)
                c.rect(xl + col_criterio + col_checkbox, y - 2, col_obs, row_h - 2, fill=1, stroke=0)
                c.setFillColorRGB(1, 1, 1)
                c.setFont('Helvetica-Bold', 8)
                c.drawString(xl + 3, y + 3, 'Criterio')
                c.drawString(xl + col_criterio + 3, y + 3, 'Sí/No')
                c.drawString(xl + col_criterio + col_checkbox + 3, y + 3, 'Observaciones')

            tbl_header()
            y -= row_h

            for item in items:
                if y < 0.85 * inch:
                    c.showPage()
                    header_pdf()
                    y = h - 1.15 * inch
                    tbl_header()
                    y -= row_h
                criterio = (item.item.criterio or '—')[:50]
                puntaje = item.puntaje
                obs = (item.observaciones or '—')[:50]
                
                c.setFillColorRGB(0.97, 0.97, 0.97)
                c.rect(xl, y - 2, col_criterio, row_h - 2, fill=1, stroke=0)
                c.rect(xl + col_criterio, y - 2, col_checkbox, row_h - 2, fill=1, stroke=0)
                c.rect(xl + col_criterio + col_checkbox, y - 2, col_obs, row_h - 2, fill=1, stroke=0)
                c.setFillColorRGB(0, 0, 0)
                c.setFont('Helvetica', 8)
                c.drawString(xl + 3, y + 3, criterio)
                
                # Checkbox Sí/No
                c.setFont('Helvetica-Bold', 9)
                checkbox_text = '✓ Sí' if puntaje == 1 else '✗ No'
                c.drawString(xl + col_criterio + 3, y + 3, checkbox_text)
                
                c.drawString(xl + col_criterio + col_checkbox + 3, y + 3, obs)
                y -= row_h

        y -= 0.1 * inch
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.5)
        c.line(xl, y + 0.1 * inch, w - 0.75 * inch, y + 0.1 * inch)
        c.setFont('Helvetica-Oblique', 8)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(w / 2, 0.55 * inch,
                            'Generado por Sistema de Gestion de Sustentaciones SENA')
        c.showPage()
        c.save()
        buf.seek(0)
        r = HttpResponse(buf, content_type='application/pdf')
        r['Content-Disposition'] = (
            f'attachment; filename="evaluacion_{evaluacion.id}_{aprendiz.documento}.pdf"'
        )
        return r

    except Exception as exc:
        messages.error(request, f'No se pudo generar el PDF: {exc}')
        return redirect('jurado_mis_evaluaciones')
