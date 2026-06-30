from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.core.mail import send_mail
from django.core.mail import BadHeaderError
from django.db.models import Q
from smtplib import SMTPAuthenticationError
from django.views.decorators.csrf import csrf_exempt
import logging
import re
import uuid
import base64

logger = logging.getLogger(__name__)

from django.conf import settings
from django.db import models
from .models import Usuario
from apps.evaluacion.models import Aprendiz, Evaluacion, Checklist, Invitacion, Resultado, GAES, Ficha, Fase


SPECIAL_PASSWORD_PATTERN = re.compile(r"[^A-Za-z0-9'\"`]")


def is_password_valid(password: str) -> bool:
    return 6 <= len(password or '') <= 8 and bool(SPECIAL_PASSWORD_PATTERN.search(password or ''))


# ==========================================================
# VISTAS de administración de usuarios (login, CRUD básico)
# ==========================================================
# Nota: nuevas secciones de “tablas” usan apps/usuarios/views_instructor_tables.py


def login_view(request):
    """Autenticación y redirección por rol.

    - POST: valida credenciales con `authenticate` y hace login.
    - GET: muestra el formulario de acceso.
    """
    if request.method == 'POST':
        # Lectura de credenciales desde el formulario
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Verificación de usuario contra la configuración de AUTH
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Login exitoso
            login(request, user)

            # Redirección basada en rol del usuario
            # Prioridad: superuser -> admin, luego rol normal
            if user.is_superuser or user.rol == 'administrador':
                return redirect('dashboard_admin')
            elif user.rol == 'instructor':
                return redirect('dashboard_instructor')
            elif user.rol == 'jurado':
                return redirect('dashboard_jurado')
            elif user.rol == 'aprendiz':
                return redirect('dashboard_aprendiz')
            else:
                return redirect('dashboard_admin')

        # Credenciales inválidas
        messages.error(request, 'Usuario o contraseña incorrectos')

    # Render del template para GET o POST fallido
    return render(request, 'auth/login.html')


@login_required
def logout_view(request):
    """Cierra la sesión del usuario y redirige al login."""
    # Django requiere CSRF en POST; el frontend debe enviar el token.
    logout(request)
    request.session.flush()
    return redirect('/usuarios/login/?logout=1')


@login_required
def perfil_usuario(request):
    """Muestra el perfil del usuario autenticado y permite cambiar la contraseña."""
    usuario = request.user
    aprendiz = None
    try:
        aprendiz = Aprendiz.objects.select_related('ficha', 'gaes', 'fase').get(usuario=usuario)
    except Aprendiz.DoesNotExist:
        pass

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cambiar_password':
            password_actual = request.POST.get('password_actual', '')
            password_nuevo = request.POST.get('password_nuevo', '')
            password_confirmar = request.POST.get('password_confirmar', '')

            if not usuario.check_password(password_actual):
                messages.error(request, 'La contraseña actual es incorrecta.')
            elif password_nuevo != password_confirmar:
                messages.error(request, 'La nueva contraseña y la confirmación no coinciden.')
            elif len(password_nuevo) < 4:
                messages.error(request, 'La contraseña debe tener al menos 4 caracteres.')
            else:
                usuario.set_password(password_nuevo)
                usuario.save()
                messages.success(request, 'Contraseña actualizada correctamente.')
                return redirect('perfil_usuario')

    return render(request, 'usuarios/perfil_usuario.html', {
        'usuario': usuario,
        'aprendiz': aprendiz,
    })


@login_required
def dashboard_admin(request):
    """Dashboard del administrador.

    Calcula conteos globales y muestra invitaciones pendientes.
    Pasa los datos de gráficas por contexto para renderizado directo en plantilla.
    """
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    # Métricas principales del sistema
    usuarios = Usuario.objects.all().count()
    fichas = Ficha.objects.all().count()
    aprendices = Aprendiz.objects.all().count()
    evaluaciones = Evaluacion.objects.all().count()
    checklists = Checklist.objects.all().count()

    # Datos para gráficas
    from django.db.models import Count
    gaes_qs = (GAES.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .filter(cant__gt=0)
               .order_by('nombre'))
    gaes_labels = [g.nombre for g in gaes_qs]
    gaes_values = [g.cant for g in gaes_qs]

    ficha_qs = (Ficha.objects
                .annotate(cant=Count('aprendices', distinct=True))
                .filter(cant__gt=0)
                .order_by('numero'))
    ficha_labels = [f.numero for f in ficha_qs]
    ficha_values = [f.cant for f in ficha_qs]

    fase_qs = (Fase.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .order_by('numero'))
    fase_labels = [f'Fase {f.numero}' for f in fase_qs]
    fase_values = [f.cant for f in fase_qs]

    return render(request, 'usuarios/dashboard_admin.html', {
        'usuarios': usuarios,
        'fichas': fichas,
        'fichas_count': fichas,
        'aprendices': aprendices,
        'evaluaciones': evaluaciones,
        'checklists': checklists,
        'gaes_labels': gaes_labels,
        'gaes_values': gaes_values,
        'ficha_labels': ficha_labels,
        'ficha_values': ficha_values,
        'fase_labels': fase_labels,
        'fase_values': fase_values,
    })



@login_required
def admin_ficha_resultados(request):
        """Admin panel: list of fichas with results, leading to GAES and then to apprentice results."""
        if request.user.rol != 'administrador':
            return HttpResponseForbidden('No tienes acceso a esta sección')

        # Get fichas that have at least one aprendiz with a Resultado
        fichas = Ficha.objects.filter(
            aprendices__resultados__isnull=False
        ).distinct().select_related('gaes', 'trimestre').prefetch_related('aprendices')

        # Optional search
        search = request.GET.get('search', '')
        if search:
            fichas = fichas.filter(
                Q(numero__icontains=search) |
                Q(programa__icontains=search) |
                Q(gaes__nombre__icontains=search)
            )

        return render(request, 'usuarios/admin_ficha_resultados.html', {
            'fichas': fichas,
            'search': search,
        })


@login_required
def dashboard_instructor(request):
    """Dashboard del instructor.
    
    Para los datos de evaluación se usa el rol='jurado' (ver comentario del mapeo).
    """
    from apps.evaluacion.models import Evaluacion, Resultado, Invitacion
    
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden('No tienes acceso a esta sección')

    # Listado total y conteo de aprendices (filtrado según permisos)
    if request.user.rol == 'administrador':
        # Los administradores ven todos los aprendices
        aprendices = Aprendiz.objects.all()
    elif request.user.rol == 'instructor':
        # Los instructores ven aprendices de sus fichas, del GAES de esas fichas
        # y donde ellos son propietarios
        aprendices = Aprendiz.objects.filter(
            models.Q(ficha__instructor=request.user)
            | models.Q(gaes__ficha__instructor=request.user)
            | models.Q(propietario=request.user)
        ).select_related('ficha', 'gaes', 'gaes__ficha', 'fase').distinct()
    elif request.user.rol == 'jurado':
        # Los jurados ven aprendices de:
        # 1. Priorizar aprendices donde ellos son propietarios (su ficha original)
        # 2. Fichas donde ellos son instructores principales
        # 3. Fichas de invitaciones aceptadas
        # 4. Fichas de evaluaciones realizadas
        
        # PRIORIDAD 1: Aprendices donde el usuario es propietario
        aprendices_propietario = Aprendiz.objects.filter(
            propietario=request.user
        ).values_list('id', flat=True).distinct()
        
        if aprendices_propietario:
            aprendices = Aprendiz.objects.filter(id__in=aprendices_propietario)
        elif mis_fichas_ids:
            aprendices = Aprendiz.objects.filter(ficha__id__in=mis_fichas_ids)
        else:
            aprendices = Aprendiz.objects.none()
    else:
        # Otros roles no ven aprendices
        aprendices = Aprendiz.objects.none()
    
    total_aprendices = aprendices.count()
    logger.info(f"dashboard_instructor: user={request.user.username}, rol={request.user.rol}, total_aprendices={total_aprendices}")

    # Fichas visibles para este usuario (propias, invitaciones, propietario)
    if request.user.rol == 'jurado':
        mis_fichas_ids = set(Ficha.objects.filter(
            instructor=request.user
        ).values_list('id', flat=True))
        inv_fichas = Invitacion.objects.filter(
            models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas)
        eval_fichas = Evaluacion.objects.filter(
            juror=request.user
        ).values_list('aprendiz__ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(eval_fichas)
        if not mis_fichas_ids:
            mis_fichas_ids = set()
    elif request.user.rol == 'instructor':
        mis_fichas_ids = set(Ficha.objects.filter(instructor=request.user).values_list('id', flat=True))
        inv_fichas = Invitacion.objects.filter(
            models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
            estado=Invitacion.ESTADO_ACEPTADA
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(inv_fichas)
        propietario_fichas = Aprendiz.objects.filter(
            propietario=request.user
        ).values_list('ficha_id', flat=True).distinct()
        mis_fichas_ids |= set(propietario_fichas)
    else:
        mis_fichas_ids = set()

    # --- Mapeo de datos para mostrar evaluaciones ---
    # En el dataset actual, `Invitacion` guarda `instructor_invitado` con rol='instructor'
    # y no con rol='jurado'. Por eso el mapeo vía Invitacion no produce coincidencias
    # directas con Evaluacion.juror.
    # Para que el panel no quede vacío, se muestran últimas evaluaciones hechas por jurados.
    jurados_relacionados = Usuario.objects.filter(rol='jurado').values_list('id', flat=True)

    # Últimas evaluaciones relacionadas a esos jurados, SOLO de mis fichas
    evaluaciones = (
        Evaluacion.objects.filter(juror__in=jurados_relacionados)
        .filter(aprendiz__ficha__id__in=mis_fichas_ids)
        .select_related('aprendiz', 'checklist', 'juror')
        .order_by('-fecha')[:10]
    )

    # Registro informativo (diagnóstico)
    evaluaciones_count = evaluaciones.count()
    logger.info(
        "dashboard_instructor: evaluaciones_count=%s para user_id=%s (rol=%s)",
        evaluaciones_count,
        request.user.id,
        getattr(request.user, 'rol', None),
    )

    # Resultados (calificaciones finales) asociados a las evaluaciones de esos jurados
    resultados = (
        Resultado.objects.filter(
            aprendiz__evaluaciones__juror__in=jurados_relacionados,
            aprendiz__ficha__id__in=mis_fichas_ids
        )
        .select_related('aprendiz')
        .distinct()
        .order_by('-fecha_cierre')[:10]
    )

    # Invitaciones pendientes para este usuario (instructor que puede ser invitado a jurado)
    invitaciones_recibidas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user)
    )
    invitaciones_pendientes = invitaciones_recibidas.filter(
        estado=Invitacion.ESTADO_PENDIENTE,
    ).select_related('instructor', 'ficha')  # Para optimizar la consulta

    # Invitaciones de este usuario hacia otros instructores (que ha enviado)
    # Solo mostrar invitaciones de fichas que el usuario puede gestionar
    mis_fichas = Ficha.objects.filter(id__in=mis_fichas_ids)
    mis_invitaciones = Invitacion.objects.filter(
        instructor=request.user,
        ficha__in=mis_fichas
    ).select_related('ficha', 'instructor_invitado')

    # Resultados de los aprendices evaluados por este instructor (si también actúa como jurado)
    evaluados_ids = Evaluacion.objects.filter(juror=request.user).values_list('aprendiz_id', flat=True).distinct()
    resultados_propio = Resultado.objects.filter(aprendiz_id__in=evaluados_ids).select_related('aprendiz').order_by('-fecha_cierre')[:10]

    # Fichas asignadas a este instructor (con competencias, fase y trimestre precargados)
    mis_fichas = Ficha.objects.filter(
        instructor=request.user
    ).prefetch_related(
        'competencias__fase', 'trimestre', 'gaes'
    ).order_by('numero')
    
    mis_fichas_ids = set(mis_fichas.values_list('id', flat=True))
    
    # También incluir fichas de aprendices donde el usuario es propietario
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(propietario_fichas)

    # ── Datos para gráficas ────────────────────────────────────────
    from django.db.models import Count

    # GAES de las fichas del instructor + GAES de aprendices propietarios
    gaes_qs = (GAES.objects
               .filter(models.Q(fichas__instructor=request.user) | models.Q(aprendices__propietario=request.user))
               .annotate(cant=Count('aprendices', distinct=True))
               .filter(cant__gt=0)
               .order_by('nombre'))

    ficha_qs = (Ficha.objects
                .filter(id__in=mis_fichas_ids)
                .annotate(cant=Count('aprendices', distinct=True))
                .filter(cant__gt=0)
                .order_by('numero'))

    _mis_fases_ids = (Aprendiz.objects
                      .filter(ficha__id__in=mis_fichas_ids)
                      .filter(fase__isnull=False)
                      .values_list('fase_id', flat=True)
                      .distinct())
    fase_qs = (Fase.objects
               .filter(id__in=_mis_fases_ids)
               .annotate(cant=Count('aprendices', distinct=True))
               .filter(cant__gt=0)
               .order_by('numero'))

    gaes_labels = [g.nombre for g in gaes_qs]
    gaes_values = [g.cant for g in gaes_qs]
    ficha_labels = [f.numero for f in ficha_qs]
    ficha_values = [f.cant for f in ficha_qs]
    fase_labels = [f'Fase {f.numero}' for f in fase_qs]
    fase_values = [f.cant for f in fase_qs]




    return render(request, 'usuarios/dashboard_instructor.html', {
        'total_aprendices': total_aprendices,
        'evaluaciones': evaluaciones,
        'resultados': resultados,
        'invitaciones_pendientes': invitaciones_pendientes,
        'mis_invitaciones': mis_invitaciones,
        'resultados_propio': resultados_propio,
        'gaes_labels': gaes_labels,
        'gaes_values': gaes_values,
        'ficha_labels': ficha_labels,
        'ficha_values': ficha_values,
        'fase_labels': fase_labels,
        'fase_values': fase_values,
        'mis_fichas': mis_fichas,
    })


@login_required
def admin_ficha_gaes(request, ficha_id):
    """Admin panel: show GAES of a ficha with button to view apprentice results."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Get GAES that have at least one aprendiz in this ficha with a Resultado
    gaes_list = GAES.objects.filter(
        aprendiz__ficha=ficha,
        aprendiz__resultados__isnull=False
    ).distinct().order_by('nombre')
    
    # Optional search
    search = request.GET.get('search', '')
    if search:
        gaes_list = gaes_list.filter(nombre__icontains=search)
    
    return render(request, 'usuarios/admin_ficha_gaes.html', {
        'ficha': ficha,
        'gaes_list': gaes_list,
        'search': search,
    })


@login_required
def admin_gaes_aprendices(request, gaes_id):
    """Admin panel: show aprendices in a GAES with pass/fail status."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    gaes = get_object_or_404(GAES, id=gaes_id)
    
    # Get aprendices in this GAES that have a Resultado
    aprendices = Aprendiz.objects.filter(
        gaes=gaes,
        resultados__isnull=False
    ).distinct().select_related('ficha').order_by('nombres', 'apellidos')
    
    # For each aprendiz, determine if passed (promedio >= 9)
    apprendices_data = []
    for aprendiz in aprendices:
        # Get latest resultado (or any)
        resultado = aprendiz.resultados.order_by('-fecha_cierre').first()
        passed = resultado.promedio >= 9 if resultado else False
        apprendices_data.append({
            'aprendiz': aprendiz,
            'resultado': resultado,
            'passed': passed,
        })
    
    # Optional search
    search = request.GET.get('search', '')
    if search:
        apprendices_data = [item for item in apprendices_data if 
                           search.lower() in item['aprendiz'].nombres.lower() or
                           search.lower() in item['aprendiz'].apellidos.lower() or
                           search.lower() in str(item['aprendiz'].documento).lower()]
    
    return render(request, 'usuarios/admin_gaes_aprendices.html', {
        'gaes': gaes,
        'aprendices_data': apprendices_data,
        'search': search,
    })


@login_required
def dashboard_jurado(request):
    """Dashboard del jurado.
    
    Muestra invitaciones del jurado, evaluaciones realizadas, invitaciones pendientes
    y métricas del sistema para este jurado.
    """
    if request.user.rol not in ['administrador', 'jurado', 'instructor']:
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    # Invitaciones recibidas por este jurado (como instructor_invitado o como jurado en instructores_jurados)
    invitaciones_recibidas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user)
    )
    invitaciones_pendientes = invitaciones_recibidas.filter(
        estado=Invitacion.ESTADO_PENDIENTE,
    )
    invitacion_aceptada = invitaciones_recibidas.filter(
        estado=Invitacion.ESTADO_ACEPTADA,
    ).first()
    
    # Aprendices y evaluaciones de este jurado
    mis_fichas_ids = set(Ficha.objects.filter(
        instructor=request.user
    ).values_list('id', flat=True).distinct())
    
    # También incluir fichas donde el usuario es propietario de los aprendices
    propietario_fichas = Aprendiz.objects.filter(
        propietario=request.user
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(propietario_fichas)
    
    inv_fichas = Invitacion.objects.filter(
        models.Q(instructor_invitado=request.user) | models.Q(instructores_jurados=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(inv_fichas)
    
    eval_fichas = Evaluacion.objects.filter(
        juror=request.user
    ).values_list('aprendiz__ficha_id', flat=True).distinct()
    mis_fichas_ids |= set(eval_fichas)
    
    aprendices = Aprendiz.objects.filter(ficha__in=mis_fichas_ids).distinct() if mis_fichas_ids else Aprendiz.objects.none()
    evaluaciones = Evaluacion.objects.filter(juror=request.user)
    total_evaluaciones = evaluaciones.count()
    
    # Invitaciones de este jurado hacia otros instructores
    mis_invitaciones = Invitacion.objects.filter(instructor=request.user)
    
    # Resultados de los aprendices evaluados por este jurado
    evaluados_ids = Evaluacion.objects.filter(juror=request.user).values_list('aprendiz_id', flat=True).distinct()
    resultados = Resultado.objects.filter(aprendiz_id__in=evaluados_ids).select_related('aprendiz').order_by('-fecha_cierre')
    
    # Datos para gráficas
    from django.db.models import Count
    gaes_qs = (GAES.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .filter(cant__gt=0)
               .order_by('nombre'))
    gaes_labels = [g.nombre for g in gaes_qs]
    gaes_values = [g.cant for g in gaes_qs]
    
    ficha_qs = (Ficha.objects
                .annotate(cant=Count('aprendices', distinct=True))
                .filter(cant__gt=0)
                .order_by('numero'))
    ficha_labels = [f.numero for f in ficha_qs]
    ficha_values = [f.cant for f in ficha_qs]
    
    fase_qs = (Fase.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .order_by('numero'))
    fase_labels = [f'Fase {f.numero}' for f in fase_qs]
    fase_values = [f.cant for f in fase_qs]
    
# ── GAES disponibles para evaluar (según invitaciones aceptadas del jurado) ──
    ficha_ids_con_invitacion = Invitacion.objects.filter(
        models.Q(instructores_jurados=request.user) |
        models.Q(instructor_invitado=request.user),
        estado=Invitacion.ESTADO_ACEPTADA
    ).values_list('ficha_id', flat=True).distinct()
    
    gaes_a_evaluar = (GAES.objects
                      .filter(
                          models.Q(fichas__id__in=ficha_ids_con_invitacion) |
                          models.Q(aprendices__gaes__ficha__id__in=ficha_ids_con_invitacion)
                      )
                      .annotate(aprendices_count=Count('aprendices', distinct=True))
                      .filter(aprendices_count__gt=0)
                      .order_by('nombre')
                      .distinct())

    return render(request, 'usuarios/dashboard_jurado.html', {
        'aprendices': aprendices,
        'evaluaciones': evaluaciones,
        'total_evaluaciones': total_evaluaciones,
        'resultados': resultados,
        'invitaciones_pendientes': invitaciones_pendientes,
        'invitacion_aceptada': invitacion_aceptada,
        'mis_invitaciones': mis_invitaciones,
        'gaes_a_evaluar': gaes_a_evaluar,
        'gaes_labels': gaes_labels,
        'gaes_values': gaes_values,
        'ficha_labels': ficha_labels,
        'ficha_values': ficha_values,
        'fase_labels': fase_labels,
        'fase_values': fase_values,
        'gaes_count': len(gaes_labels),
        'ficha_count': len(ficha_labels),
        'fase_count': len(fase_labels),
    })


@login_required
def dashboard_aprendiz(request):
    """Dashboard del aprendiz.

    Muestra el objeto Aprendiz asociado al usuario autenticado y sus resultados.
    Incluye métricas y gráficas de desempeño general.
    """
    if request.user.rol != 'aprendiz':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    try:
        aprendiz = Aprendiz.objects.select_related('ficha', 'gaes', 'fase').get(usuario=request.user)
        resultados = aprendiz.resultados.order_by('-fecha_cierre')
        evaluaciones = aprendiz.evaluaciones.all()
        total_evaluaciones = evaluaciones.count()
        evaluaciones_completadas = evaluaciones.filter(estado=Evaluacion.ESTADO_COMPLETADA).count()
    except Aprendiz.DoesNotExist:
        aprendiz = None
        resultados = []
        evaluaciones = []
        total_evaluaciones = 0
        evaluaciones_completadas = 0

    # Datos para gráficas (igual que otros dashboards)
    from django.db.models import Count
    gaes_qs = (GAES.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .filter(cant__gt=0)
               .order_by('nombre'))
    gaes_labels = [g.nombre for g in gaes_qs]
    gaes_values = [g.cant for g in gaes_qs]

    ficha_qs = (Ficha.objects
                .annotate(cant=Count('aprendices', distinct=True))
                .filter(cant__gt=0)
                .order_by('numero'))
    ficha_labels = [f.numero for f in ficha_qs]
    ficha_values = [f.cant for f in ficha_qs]

    fase_qs = (Fase.objects
               .annotate(cant=Count('aprendices', distinct=True))
               .order_by('numero'))
    fase_labels = [f'Fase {f.numero}' for f in fase_qs]
    fase_values = [f.cant for f in fase_qs]

    return render(request, 'usuarios/dashboard_aprendiz.html', {
        'aprendiz': aprendiz,
        'resultados': resultados,
        'evaluaciones': list(evaluaciones),
        'total_evaluaciones': total_evaluaciones,
        'evaluaciones_completadas': evaluaciones_completadas,
        'gaes_labels': gaes_labels,
        'gaes_values': gaes_values,
        'ficha_labels': ficha_labels,
        'ficha_values': ficha_values,
        'fase_labels': fase_labels,
        'fase_values': fase_values,
        'gaes_count': len(gaes_labels),
        'ficha_count': len(ficha_labels),
        'fase_count': len(fase_labels),
    })


@login_required
def lista_usuarios(request):
    """Listado y búsqueda de usuarios (solo administrador)."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    def parse_search_tokens(raw: str):
        # Normaliza separadores para tokenizar la búsqueda
        raw = '' if raw is None else str(raw)
        raw = raw.replace('|', ' ').replace(',', ' ').replace(';', ' ')
        tokens = [t.strip() for t in raw.split() if t.strip()]
        return tokens[:25]

    search = request.GET.get('search', '')
    tokens = parse_search_tokens(search)

    usuarios = Usuario.objects.all()

    if tokens:
        # Construcción dinámica de búsqueda por tokens (OR por token)
        q_total = models.Q()
        for token in tokens:
            token_q = (
                models.Q(username__icontains=token) |
                models.Q(email__icontains=token) |
                models.Q(rol__icontains=token)
            )
            q_total |= token_q
        usuarios = usuarios.filter(q_total)

    return render(request, 'usuarios/lista_usuarios.html', {'usuarios': usuarios, 'search': search})


@login_required
def lista_usuarios_por_grupos(request):
    """Listado de usuarios divididos por grupos (solo administrador)."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    search = request.GET.get('search', '')
    filtro_rol = request.GET.get('filtro_rol', '')
    filtro_activo = request.GET.get('filtro_activo', '')

    # Separar usuarios por grupos
    usuarios_admin = Usuario.objects.filter(rol='administrador').order_by('username')
    usuarios_instructores_jurados = Usuario.objects.filter(rol__in=['instructor', 'jurado']).order_by('rol', 'username')
    usuarios_aprendices = Usuario.objects.filter(rol='aprendiz').order_by('username')

    from django.db.models import Count
    fichas_con_aprendices = Ficha.objects.annotate(
        num_aprendices=Count('aprendices', distinct=True)
    ).filter(num_aprendices__gt=0).order_by('numero')

    # Aplicar búsqueda general
    if search:
        q_search = (
            models.Q(username__icontains=search) |
            models.Q(email__icontains=search)
        )
        usuarios_admin = usuarios_admin.filter(q_search)
        usuarios_instructores_jurados = usuarios_instructores_jurados.filter(q_search)
        usuarios_aprendices = usuarios_aprendices.filter(q_search)

    # Aplicar filtro por rol - si se filtra por un rol específico, ocultar otros grupos
    if filtro_rol:
        if filtro_rol == 'instructor':
            usuarios_instructores_jurados = Usuario.objects.filter(rol='instructor').order_by('username')
            usuarios_admin = Usuario.objects.none()
            usuarios_aprendices = Usuario.objects.none()
        elif filtro_rol == 'jurado':
            usuarios_instructores_jurados = Usuario.objects.filter(rol='jurado').order_by('username')
            usuarios_admin = Usuario.objects.none()
            usuarios_aprendices = Usuario.objects.none()
        elif filtro_rol == 'aprendiz':
            usuarios_aprendices = Usuario.objects.filter(rol='aprendiz').order_by('username')
            usuarios_admin = Usuario.objects.none()
            usuarios_instructores_jurados = Usuario.objects.none()
        elif filtro_rol == 'administrador':
            usuarios_admin = Usuario.objects.filter(rol='administrador').order_by('username')
            usuarios_instructores_jurados = Usuario.objects.none()
            usuarios_aprendices = Usuario.objects.none()

    # Aplicar filtro por estado
    if filtro_activo == 'true':
        usuarios_admin = usuarios_admin.filter(is_active=True)
        usuarios_instructores_jurados = usuarios_instructores_jurados.filter(is_active=True)
        usuarios_aprendices = usuarios_aprendices.filter(is_active=True)
    elif filtro_activo == 'false':
        usuarios_admin = usuarios_admin.filter(is_active=False)
        usuarios_instructores_jurados = usuarios_instructores_jurados.filter(is_active=False)
        usuarios_aprendices = usuarios_aprendices.filter(is_active=False)

    return render(request, 'usuarios/lista_usuarios_por_grupos.html', {
        'usuarios_admin': usuarios_admin,
        'usuarios_instructores_jurados': usuarios_instructores_jurados,
        'usuarios_aprendices': usuarios_aprendices,
        'fichas_con_aprendices': fichas_con_aprendices,
        'search': search,
        'filtro_rol': filtro_rol,
        'filtro_activo': filtro_activo,
    })


@login_required
def crear_usuario(request):
    """Crea un usuario (CRUD) - solo administrador."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        rol = request.POST.get('rol')
        form_data = request.POST.dict()

        if not is_password_valid(password):
            messages.error(
                request,
                'La contraseña debe tener entre 6 y 8 caracteres e incluir un símbolo especial distinto a comillas.'
            )
            return render(request, 'usuarios/crear_usuario.html', {'form_data': form_data})

        usuario = Usuario.objects.create_user(
            username=username,
            password=password,
            email=email,
            rol=rol,
        )

        messages.success(request, f'Usuario {username} creado exitosamente')
        return redirect('lista_usuarios_por_grupos')

    # GET: muestra el formulario
    return render(request, 'usuarios/crear_usuario.html')


@login_required
def editar_usuario(request, usuario_id):
    """Edita información de un usuario (solo administrador)."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    usuario = Usuario.objects.get(id=usuario_id)

    if request.method == 'POST':
        # Actualiza email/rol; si hay password, se re-cifra
        usuario.email = request.POST.get('email')
        usuario.rol = request.POST.get('rol')
        password = request.POST.get('password')

        if password:
            usuario.set_password(password)

        usuario.save()
        messages.success(request, 'Usuario actualizado exitosamente')
        return redirect('lista_usuarios_por_grupos')

    # GET: muestra la plantilla con el objeto actual
    return render(request, 'usuarios/editar_usuario.html', {'usuario': usuario})


@login_required
def eliminar_usuario(request, usuario_id):
    """Elimina un usuario (solo administrador) con confirmación de dependencias."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    usuario = Usuario.objects.get(id=usuario_id)
    
    # Verificar dependencias antes de intentar eliminar
    dependencias = []
    
    # Invitaciones creadas
    invitaciones_creadas = Invitacion.objects.filter(instructor=usuario).count()
    if invitaciones_creadas > 0:
        dependencias.append({'tipo': 'invitaciones_creadas', 'texto': f"Ha creado {invitaciones_creadas} invitación(es)"})
    
    # Invitaciones recibidas
    invitaciones_recibidas = Invitacion.objects.filter(instructor_invitado=usuario).count()
    if invitaciones_recibidas > 0:
        dependencias.append({'tipo': 'invitaciones_recibidas', 'texto': f"Es invitado en {invitaciones_recibidas} invitación(es)"})
    
    # Invitaciones como jurado
    invitaciones_jurado = Invitacion.objects.filter(instructores_jurados=usuario).count()
    if invitaciones_jurado > 0:
        dependencias.append({'tipo': 'invitaciones_jurado', 'texto': f"Es jurado en {invitaciones_jurado} invitación(es)"})
    
    # Fichas asignadas
    fichas_asignadas = Ficha.objects.filter(instructor=usuario).count()
    if fichas_asignadas > 0:
        dependencias.append({'tipo': 'fichas_asignadas', 'texto': f"Tiene {fichas_asignadas} ficha(s) asignada(s)"})
    
    # Evaluaciones realizadas
    evaluaciones_realizadas = Evaluacion.objects.filter(juror=usuario).count()
    if evaluaciones_realizadas > 0:
        dependencias.append({'tipo': 'evaluaciones_realizadas', 'texto': f"Ha realizado {evaluaciones_realizadas} evaluación(es)"})
    
    # Aprendices propietarios
    aprendices_propietario = Aprendiz.objects.filter(propietario=usuario).count()
    if aprendices_propietario > 0:
        dependencias.append({'tipo': 'aprendices_propietario', 'texto': f"Es propietario de {aprendices_propietario} aprendiz(s)"})
    
    # Checklists creados
    checklists_creados = Checklist.objects.filter(propietario=usuario).count()
    if checklists_creados > 0:
        dependencias.append({'tipo': 'checklists_creados', 'texto': f"Ha creado {checklists_creados} checklist(s)"})
    
    if dependencias:
        return render(request, 'usuarios/confirmar_eliminacion.html', {
            'usuario': usuario,
            'dependencias': dependencias,
        })
    
    usuario.delete()
    messages.success(request, 'Usuario eliminado exitosamente')
    return redirect('lista_usuarios_por_grupos')


@login_required
def eliminar_usuario_confirmar(request, usuario_id):
    """Elimina un usuario confirmando que se eliminan sus dependencias."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    if request.method == 'POST':
        usuario = Usuario.objects.get(id=usuario_id)
        respaldar = request.POST.get('respaldar_datos') == 'on'
        
        if respaldar:
            pdf_response = generar_respaldo_usuario(usuario)
            token = uuid.uuid4().hex
            request.session[f'respaldo_token_{token}'] = base64.b64encode(pdf_response.content).decode('ascii')
            request.session['respaldo_pending'] = token
        
        # Eliminar todas las dependencias relacionadas
        Invitacion.objects.filter(instructor=usuario).delete()
        Invitacion.objects.filter(instructor_invitado=usuario).delete()
        Invitacion.objects.filter(instructores_jurados=usuario).delete()
        Ficha.objects.filter(instructor=usuario).delete()
        Evaluacion.objects.filter(juror=usuario).delete()
        Aprendiz.objects.filter(propietario=usuario).delete()
        Checklist.objects.filter(propietario=usuario).delete()
        
        usuario.delete()
        
        if respaldar:
            messages.success(request, f'Usuario {usuario.username} eliminado. El respaldo se descargará en breve.')
            return redirect('respaldo_exito')
        else:
            messages.success(request, f'Usuario {usuario.username} y todas sus dependencias han sido eliminados.')
            return redirect('lista_usuarios_por_grupos')
    
    return redirect('lista_usuarios_por_grupos')


@login_required
def respaldo_exito(request):
    """Página intermedia que dispara la descarga del PDF y redirige automáticamente."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    return render(request, 'usuarios/respaldo_exito.html')


@login_required
def respaldo_descargar(request):
    """Sirve el PDF de respaldo almacenado en sesión y limpia la sesión."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    token = request.session.pop('respaldo_pending', None)
    if not token:
        return HttpResponseForbidden('El respaldo ha expirado o ya fue descargado.')
    pdf_b64 = request.session.pop(f'respaldo_token_{token}', None)
    if not pdf_b64:
        return HttpResponseForbidden('El respaldo ha expirado o ya fue descargado.')
    from django.utils import timezone
    pdf_bytes = base64.b64decode(pdf_b64)
    filename = f"respaldo_usuario_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def generar_respaldo_usuario(usuario):
    """Genera un PDF con la información del usuario antes de eliminar."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from io import BytesIO
    from django.http import HttpResponse
    from django.utils import timezone
    from collections import defaultdict

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=1*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a252f'),
        alignment=1,
        fontName='Helvetica-Bold',
        spaceAfter=6,
    )

    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.white,
        spaceAfter=8,
        spaceBefore=14,
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#2c3e50'),
        leftIndent=0,
        rightIndent=0,
        borderPadding=5,
    )

    subsection_style = ParagraphStyle(
        'SubSection',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=4,
        fontName='Helvetica-Bold',
        leftIndent=4,
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
    )

    empty_style = ParagraphStyle(
        'Empty',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=1,
        spaceAfter=6,
    )

    elements = []

    elements.append(Paragraph("Respaldo de Usuario - Sistema SENA", title_style))
    elements.append(Paragraph("Evalia", ParagraphStyle(
        'SubTitle', parent=styles['Normal'], fontSize=11, alignment=1, spaceAfter=12
    )))

    elements.append(Paragraph("Información del Usuario", section_style))

    fecha_ingreso = getattr(usuario, 'date_joined', None)
    fecha_eliminacion = timezone.now()
    if fecha_ingreso:
        tiempo = fecha_eliminacion - fecha_ingreso
        duracion_dias = tiempo.days
        duracion_str = f"{duracion_dias} días"
    else:
        duracion_dias = None
        duracion_str = "No registrado"

    user_data = [
        ['Usuario:', usuario.username],
        ['Email:', usuario.email],
        ['Rol:', usuario.get_rol_display()],
        ['Fecha de ingreso:', fecha_ingreso.strftime('%d/%m/%Y') if fecha_ingreso else 'No registrada'],
        ['Fecha de eliminación:', fecha_eliminacion.strftime('%d/%m/%Y %H:%M')],
        ['Tiempo en la empresa:', duracion_str],
    ]
    user_table = Table(user_data, colWidths=[2.2*inch, 3.5*inch])
    user_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(user_table)
    elements.append(Spacer(1, 0.05*inch))

    # Fichas Asignadas
    fichas = Ficha.objects.filter(instructor=usuario).select_related('trimestre')
    elements.append(Paragraph("Fichas Asignadas", section_style))
    if fichas.exists():
        ficha_data = [['Número', 'Programa', 'Trimestre', 'Jornada', 'Estado']]
        for f in fichas:
            trim = f"Trim {f.trimestre.numero} ({f.trimestre.anio})" if f.trimestre else 'Sin trimestre'
            ficha_data.append([
                f.numero,
                f.programa or 'Sin programa',
                trim,
                f.get_jornada_display(),
                f.get_estado_display(),
            ])
        ficha_table = Table(ficha_data, colWidths=[1.1*inch, 1.6*inch, 1.3*inch, 1*inch, 0.9*inch])
        ficha_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(ficha_table)
    else:
        elements.append(Paragraph("Este usuario no tenía fichas asignadas.", empty_style))
        elements.append(Table([['']], colWidths=[5.7*inch], rowHeights=[0.2*inch]))
    elements.append(Spacer(1, 0.05*inch))

    # Invitaciones Recibidas
    invitaciones_recibidas = Invitacion.objects.filter(instructor_invitado=usuario).select_related('ficha')
    elements.append(Paragraph("Invitaciones Recibidas", section_style))
    if invitaciones_recibidas.exists():
        inv_data = [['Ficha', 'Estado', 'Fecha de envío']]
        for inv in invitaciones_recibidas:
            ficha_num = inv.ficha.numero if inv.ficha else 'Sin ficha'
            inv_data.append([
                ficha_num,
                inv.get_estado_display(),
                inv.fecha_envio.strftime('%d/%m/%Y') if inv.fecha_envio else 'N/A',
            ])
        inv_table = Table(inv_data, colWidths=[1.5*inch, 1.5*inch, 2.7*inch])
        inv_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(inv_table)
    else:
        elements.append(Paragraph("No tenía invitaciones recibidas.", empty_style))
        elements.append(Table([['']], colWidths=[5.7*inch], rowHeights=[0.2*inch]))
    elements.append(Spacer(1, 0.05*inch))

    # Invitaciones Creadas
    invitaciones_creadas = Invitacion.objects.filter(instructor=usuario).select_related('ficha')
    elements.append(Paragraph("Invitaciones Creadas", section_style))
    if invitaciones_creadas.exists():
        inv_data = [['Ficha', 'Estado', 'Fecha de envío']]
        for inv in invitaciones_creadas:
            ficha_num = inv.ficha.numero if inv.ficha else 'Sin ficha'
            inv_data.append([
                ficha_num,
                inv.get_estado_display(),
                inv.fecha_envio.strftime('%d/%m/%Y') if inv.fecha_envio else 'N/A',
            ])
        inv_table = Table(inv_data, colWidths=[1.5*inch, 1.5*inch, 2.7*inch])
        inv_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(inv_table)
    else:
        elements.append(Paragraph("No tenía invitaciones creadas.", empty_style))
        elements.append(Table([['']], colWidths=[5.7*inch], rowHeights=[0.2*inch]))
    elements.append(Spacer(1, 0.05*inch))

    # Evaluaciones como Jurado organizadas por Ficha
    evaluaciones = Evaluacion.objects.filter(juror=usuario).select_related('aprendiz', 'aprendiz__ficha', 'checklist')
    elements.append(Paragraph("Evaluaciones como Jurado", section_style))
    if evaluaciones.exists():
        por_ficha = defaultdict(list)
        for ev in evaluaciones:
            ficha = ev.aprendiz.ficha if ev.aprendiz and ev.aprendiz.ficha else None
            ficha_key = ficha.numero if ficha else 'Sin ficha'
            por_ficha[ficha_key].append(ev)

        for ficha_num, evals in sorted(por_ficha.items()):
            elements.append(Paragraph(f"Ficha: {ficha_num}", subsection_style))
            ev_data = [['Aprendiz', 'Documento', 'Checklist', 'Calificación', 'Fecha']]
            for ev in evals:
                ap = ev.aprendiz
                nombre = f"{ap.nombres} {ap.apellidos}" if ap else 'Sin aprendiz'
                doc = ap.documento if ap else 'N/A'
                ev_data.append([
                    nombre,
                    doc,
                    ev.checklist.titulo,
                    str(ev.calificacion_total),
                    ev.fecha.strftime('%d/%m/%Y') if ev.fecha else 'N/A',
                ])
            ev_table = Table(ev_data, colWidths=[1.7*inch, 1*inch, 1.4*inch, 0.9*inch, 0.9*inch])
            ev_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5d6d7e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(ev_table)
            elements.append(Spacer(1, 0.05*inch))
    else:
        elements.append(Paragraph("No realizó evaluaciones como jurado.", empty_style))
        elements.append(Table([['']], colWidths=[5.7*inch], rowHeights=[0.2*inch]))
    elements.append(Spacer(1, 0.05*inch))

    # Aprendices Propietarios
    aprendices = Aprendiz.objects.filter(propietario=usuario).select_related('ficha')
    elements.append(Paragraph("Aprendices Propietarios", section_style))
    if aprendices.exists():
        apr_data = [['Nombre', 'Documento', 'Email', 'Ficha']]
        for apr in aprendices:
            ficha_num = apr.ficha.numero if apr.ficha else 'Sin ficha'
            apr_data.append([f"{apr.nombres} {apr.apellidos}", apr.documento, apr.email, ficha_num])
        apr_table = Table(apr_data, colWidths=[1.8*inch, 1.1*inch, 1.7*inch, 1.1*inch])
        apr_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(apr_table)
    else:
        elements.append(Paragraph("No era propietario de aprendices.", empty_style))
        elements.append(Table([['']], colWidths=[5.7*inch], rowHeights=[0.2*inch]))

    doc.build(elements)
    buffer.seek(0)

    filename = f"respaldo_usuario_{usuario.username}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def lista_instructores(request):
    """Lista de instructores y jurados (solo administrador) con búsqueda."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    def parse_search_tokens(raw: str):
        raw = '' if raw is None else str(raw)
        raw = raw.replace('|', ' ').replace(',', ' ').replace(';', ' ')
        tokens = [t.strip() for t in raw.split() if t.strip()]
        return tokens[:25]

    search = request.GET.get('search', '')
    tokens = parse_search_tokens(search)

    # Se precargan relaciones para mejorar performance al mostrar conteos
    instructores = Usuario.objects.filter(rol__in=['instructor', 'jurado']).prefetch_related('invitaciones_recibidas')

    if tokens:
        q_total = models.Q()
        for token in tokens:
            token_q = (
                models.Q(username__icontains=token) |
                models.Q(email__icontains=token)
            )

            # Si el token coincide con un rol, también filtra exactamente por rol
            if token.lower() in ['instructor', 'jurado']:
                token_q |= models.Q(rol=token.lower())

            q_total |= token_q

        instructores = instructores.filter(q_total)

    return render(request, 'usuarios/lista_instructores.html', {
        'instructores': instructores,
        'search': search,
    })


@login_required
def enviar_invitacion_email(request, instructor_id):
    """Crea invitación y envía email para que un instructor se convierta en jurado."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    instructor = get_object_or_404(Usuario, id=instructor_id, rol='instructor')

    if request.method == 'POST':
        # Mensaje opcional enviado por el administrador
        mensaje = request.POST.get('mensaje', '')
        fecha_evaluacion = request.POST.get('fecha_evaluacion')
        hora_evaluacion = request.POST.get('hora_evaluacion')

        # --- 1) Persistencia de invitación ---
        jurados_ids = request.POST.getlist('jurados')
        invitacion = Invitacion.objects.create(
            instructor=request.user,
            instructor_invitado=instructor,
            mensaje=mensaje,
            fecha_evaluacion=fecha_evaluacion,
            hora_evaluacion=hora_evaluacion if hora_evaluacion else None
        )

        # Agregar jurados seleccionados (pueden ser instructores)
        if jurados_ids:
            invitacion.instructores_jurados.set(Usuario.objects.filter(id__in=jurados_ids, rol='instructor'))

        # --- 2) Construcción de links de acción ---
        subject = 'Invitación para ser Jurado - Sistema SENA'
        link_aceptar = request.build_absolute_uri(f'/evaluacion/aceptar-invitacion/{invitacion.id}/')
        link_rechazar = request.build_absolute_uri(f'/evaluacion/rechazar-invitacion/{invitacion.id}/')

        ficha_numero = 'Asignada posteriormente'
        try:
            # Intentamos obtener la ficha del instructor si tiene aprendices asignados
            aprendiz = Aprendiz.objects.filter(usuario=instructor).first()
            if aprendiz and aprendiz.ficha:
                ficha_numero = aprendiz.ficha.numero
        except:
            pass

        email_body = f"""
Hola {instructor.username},

Te han invitado a participar como jurado en el sistema de sustentaciones SENA.

Ficha: {ficha_numero}
Fecha de evaluación: {fecha_evaluacion}
Hora de evaluación: {hora_evaluacion or 'Por definir'}

Mensaje: {mensaje}

Aceptar: {link_aceptar}
Rechazar: {link_rechazar}

¡Saludos!
Admin: {request.user.username}
        """

        try:
            # --- 3) Envío de correo SMTP ---
            send_mail(
                subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [instructor.email],
                fail_silently=False,
            )

        except SMTPAuthenticationError:
            # Error típico de credenciales Gmail / App Password
            logger.exception("SMTPAuthenticationError al enviar invitación")
            messages.error(
                request,
                "No se pudo enviar la invitación por autenticación SMTP (credenciales). Revisa EMAIL_HOST_USER/EMAIL_HOST_PASSWORD (Gmail App Password).",
            )
            return redirect('lista_instructores')

        except Exception as e:
            logger.exception(f"Error inesperado al enviar invitación: {e}")
            messages.error(request, f"Error inesperado: {e}")
            return redirect('lista_instructores')

        messages.success(request, f'Invitación enviada exitosamente a {instructor.email}. Está a la espera de la confirmación.')
        return redirect('lista_instructores')

    # Para GET, mostrar formulario
    # Obtener programa del instructor si tiene fichas
    programa = None
    try:
        aprendiz = Aprendiz.objects.filter(usuario=instructor).first()
        if aprendiz and aprendiz.ficha:
            programa = aprendiz.ficha.programa
    except:
        pass
    
    # Filtrar jurados por mismo programa (modalidad)
    if programa:
        jurados = Usuario.objects.filter(
            rol='instructor'
        ).filter(
            fichas_asignadas__programa=programa
        ).distinct()
    else:
        jurados = Usuario.objects.filter(rol='instructor')
        
    return render(request, 'usuarios/enviar_invitacion_email.html', {
        'instructor': instructor,
        'jurados': jurados
    })


@login_required
def enviar_invitacion_ficha(request, ficha_id):
    """Vista para admin enviar invitación al instructor encargado de una ficha con jurados preseleccionados."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    ficha = get_object_or_404(Ficha, id=ficha_id)

    if request.method == 'POST':
        fecha_evaluacion = request.POST.get('fecha_evaluacion')
        hora_evaluacion = request.POST.get('hora_evaluacion')
        mensaje = request.POST.get('mensaje', '')
        jurados_ids = request.POST.getlist('jurados')
        checklist_id = request.POST.get('checklist_id')

        # Crear la invitación al instructor encargado de la ficha
        invitacion = Invitacion.objects.create(
            instructor=request.user,
            instructor_invitado=ficha.instructor,
            ficha=ficha,
            fecha_evaluacion=fecha_evaluacion,
            hora_evaluacion=hora_evaluacion,
            mensaje=mensaje,
            checklist_id=checklist_id if checklist_id else None
        )

        # Agregar los jurados seleccionados (pueden ser instructores)
        if jurados_ids:
            invitacion.instructores_jurados.set(Usuario.objects.filter(id__in=jurados_ids, rol='instructor'))

        # Enviar notificación por email si hay instructor asignado
        if ficha.instructor and ficha.instructor.email:
            subject = 'Invitación para sustentación - Sistema SENA'
            jurados_nombres = ', '.join([u.username for u in invitacion.instructores_jurados.all()])
            email_body = f"""
Hola {ficha.instructor.username},

Has recibido una invitación para la sustentación de la ficha {ficha.numero}.

Fecha: {fecha_evaluacion}
Hora: {hora_evaluacion or 'Por definir'}
Jurados seleccionados: {jurados_nombres or 'Por asignar'}

Mensaje: {mensaje}

Saludos,
Administrador
            """
            try:
                send_mail(
                    subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [ficha.instructor.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.exception(f"Error enviando email: {e}")

        messages.success(request, f'Invitación enviada al instructor de la ficha {ficha.numero}')
        return redirect('detalle_ficha', pk=ficha_id)

    # GET: mostrar formulario
    # Filtrar jurados por mismo programa (modalidad) de la ficha
    jurados = Usuario.objects.filter(
        rol='instructor'
    ).filter(
        fichas_asignadas__programa=ficha.programa
    ).distinct()
    if request.user.rol == 'administrador':
        checklists = Checklist.objects.filter(activo=True)
    else:
        checklists = Checklist.objects.filter(propietario=request.user, activo=True)
    return render(request, 'usuarios/enviar_invitacion_ficha.html', {
        'ficha': ficha,
        'jurados': jurados,
        'checklists': checklists
    })


@login_required
def ver_invitacion_ficha(request, invitacion_id):
    """Vista para que el instructor encargado vea la invitación y comparta con jurados."""
    invitacion = get_object_or_404(Invitacion, id=invitacion_id)

    # Solo el instructor invitado o admin pueden ver
    if request.user != invitacion.instructor_invitado and not request.user.is_admin():
        return HttpResponseForbidden('No tienes acceso a esta invitación')

    return render(request, 'usuarios/ver_invitacion_ficha.html', {
        'invitacion': invitacion,
        'jurados': invitacion.instructores_jurados.all()
    })


@login_required
def compartir_invitacion(request, invitacion_id):
    """Vista para compartir la invitación con un jurado adicional."""
    invitacion = get_object_or_404(Invitacion, id=invitacion_id)

    if request.user.rol != 'administrador' and request.user != invitacion.instructor_invitado:
        return HttpResponseForbidden('No tienes acceso a esta invitación')

    if request.method == 'POST':
        jurado_id = request.POST.get('jurado_id')
        if jurado_id:
            jurado = get_object_or_404(Usuario, id=jurado_id, rol='instructor')
            invitacion.instructores_jurados.add(jurado)
            
            if jurado.email:
                subject = 'Invitación para ser Jurado - Sistema SENA'
                link_aceptar = request.build_absolute_uri(f'/evaluacion/aceptar-invitacion/{invitacion.id}/')
                link_rechazar = request.build_absolute_uri(f'/evaluacion/rechazar-invitacion/{invitacion.id}/')
                ficha_numero = invitacion.ficha.numero if invitacion.ficha else 'Asignada posteriormente'
                
                email_body = f"""
Hola {jurado.username},

Te han agregado como jurado adicional en una invitación para sustentación.

Ficha: {ficha_numero}
Fecha de evaluación: {invitacion.fecha_evaluacion or 'Por definir'}
Hora de evaluación: {invitacion.hora_evaluacion or 'Por definir'}

Mensaje: {invitacion.mensaje or 'Sin mensaje adicional'}

Aceptar: {link_aceptar}
Rechazar: {link_rechazar}

¡Saludos!
Equipo SENA
                """
                try:
                    send_mail(
                        subject,
                        email_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [jurado.email],
                        fail_silently=False,
                    )
                    messages.success(request, f'{jurado.username} agregado como jurado y se envió email a {jurado.email}')
                except SMTPAuthenticationError:
                    logger.exception("SMTPAuthenticationError al enviar invitación a jurado")
                    messages.warning(request, f'{jurado.username} agregado como jurado, pero no se pudo enviar el email (verifica credenciales SMTP).')
                except Exception as e:
                    logger.exception(f"Error inesperado al enviar invitación: {e}")
                    messages.warning(request, f'{jurado.username} agregado como jurado, pero no se pudo enviar el email.')
            else:
                messages.success(request, f'{jurado.username} agregado como jurado (no tiene email registrado)')
        return redirect('ver_invitacion_ficha', invitacion_id=invitacion_id)

    # GET: mostrar formulario de selección
    jurados_disponibles = Usuario.objects.filter(rol='instructor').exclude(
        id__in=invitacion.instructores_jurados.values_list('id', flat=True)
    )
    return render(request, 'usuarios/compartir_invitacion.html', {
        'invitacion': invitacion,
        'jurados_disponibles': jurados_disponibles
    })


