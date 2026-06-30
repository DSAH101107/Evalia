# apps/gaes/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import models
from django.db.models import ProtectedError, Prefetch, Q
from django.views.decorators.http import require_POST
from .models import GAES
from apps.evaluacion.models import Aprendiz, Competencia, Invitacion
from apps.fichas.models import Ficha
from apps.usuarios.models import Usuario, Rol


def _usuario_puede_gestionar_gaes(user, gaes):
    """Verifica si el usuario puede gestionar un GAES."""
    if user.rol == 'administrador':
        return True
    if user.rol == 'instructor' and gaes.ficha and gaes.ficha.instructor == user:
        return True
    return False


@login_required
def lista_fichas_gaes(request):
    """Vista para admin: lista fichas con información detallada."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    fichas = Ficha.objects.select_related('instructor', 'trimestre').prefetch_related(
        'aprendices', 'grupos'
    ).annotate(
        cant_aprendices=models.Count('aprendices', distinct=True),
        cant_gaess=models.Count('grupos', distinct=True),
    ).order_by('numero')
    return render(request, 'gaes/lista_fichas_gaes.html', {'fichas': fichas})


@login_required
def detalle_ficha_gaes(request, pk):
    """Vista para admin: detalle de ficha con GAES y aprendices."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    ficha = get_object_or_404(Ficha.objects.select_related('instructor', 'trimestre'), pk=pk)
    gaes_list = ficha.grupos.all().annotate(
        cant_aprendices=models.Count('aprendices', distinct=True)
    )
    aprendices = ficha.aprendices.all()
    return render(request, 'gaes/detalle_ficha_gaes.html', {
        'ficha': ficha,
        'gaes_list': gaes_list,
        'aprendices': aprendices,
    })


@login_required
def lista_gaes(request):
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden()
    
    from django.db.models import Q
    
    if request.user.rol == 'administrador':
        gaes_list = GAES.objects.annotate(
            cant_aprendices=models.Count('aprendices', distinct=True),
            cant_fichas=models.Count('fichas', distinct=True),
        ).order_by('nombre')
    elif request.user.rol == 'instructor':
        gaes_list = GAES.objects.filter(
            fichas__instructor=request.user
        ).annotate(
            cant_aprendices=models.Count('aprendices', distinct=True),
            cant_fichas=models.Count('fichas', distinct=True),
        ).order_by('nombre').distinct()
    else:
        gaes_list = GAES.objects.all().annotate(
            cant_aprendices=models.Count('aprendices', distinct=True),
            cant_fichas=models.Count('fichas', distinct=True),
        ).order_by('nombre')
    
    # Filtros multicriterio
    filtro_nombre = request.GET.get('filtro_nombre', '')
    filtro_descripcion = request.GET.get('filtro_descripcion', '')
    filtro_ficha = request.GET.get('filtro_ficha', '')
    search = request.GET.get('search', '')
    
    if search:
        gaes_list = gaes_list.filter(
            Q(nombre__icontains=search) |
            Q(descripcion__icontains=search)
        )
    if filtro_nombre:
        gaes_list = gaes_list.filter(nombre__icontains=filtro_nombre)
    if filtro_descripcion:
        gaes_list = gaes_list.filter(descripcion__icontains=filtro_descripcion)
    if filtro_ficha:
        gaes_list = gaes_list.filter(fichas__numero=filtro_ficha)
    
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
    
    return render(request, 'gaes/lista_gaes.html', {
        'gaes_list': gaes_list,
        'filtro_nombre': filtro_nombre,
        'filtro_descripcion': filtro_descripcion,
        'filtro_ficha': filtro_ficha,
        'search': search,
        'fichas_list': fichas_list,
    })


@login_required
def lista_gaes_instructor(request):
    """Vista específica para instructores: lista GAES por ficha."""
    from apps.evaluacion.models import Aprendiz
    if request.user.rol != 'instructor':
        return HttpResponseForbidden()
    
    mis_fichas = Ficha.objects.filter(instructor=request.user).prefetch_related(
        models.Prefetch(
            'grupos',
            queryset=GAES.objects.annotate(
                cant_aprendices=models.Count('aprendices', distinct=True),
            ).order_by('nombre')
        )
    ).order_by('numero')
    
    return render(request, 'gaes/lista_gaes_instructor.html', {
        'mis_fichas': mis_fichas,
    })


@login_required
def crear_gaes(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method == 'POST':
        GAES.objects.create(
            nombre=request.POST['nombre'],
            descripcion=request.POST.get('descripcion', ''),
        )
        messages.success(request, 'GAES creado')
        return redirect('lista_gaes')
    return render(request, 'gaes/crear_gaes.html')


@login_required
def detalle_gaes(request, pk):
    gaes = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes):
        return HttpResponseForbidden()
    aprendices_en_gaes = gaes.aprendices.filter(gaes=gaes)
    aprendices_disponibles = Aprendiz.objects.filter(
        gaes__isnull=True, usuario__rol=Rol.APRENDIZ
    ).select_related('ficha', 'usuario').order_by('nombres', 'apellidos')
    gaes_list = GAES.objects.exclude(pk=pk).order_by('nombre')
    return render(request, 'gaes/detalle_gaes.html', {
        'gaes': gaes,
        'aprendices_en_gaes': aprendices_en_gaes,
        'aprendices_disponibles': aprendices_disponibles,
        'gaes_list': gaes_list,
    })


@login_required
def editar_gaes(request, pk):
    gaes = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes):
        return HttpResponseForbidden()
    if request.method == 'POST':
        gaes.nombre = request.POST.get('nombre', gaes.nombre)
        gaes.descripcion = request.POST.get('descripcion', gaes.descripcion)
        gaes.ficha = None
        if request.POST.get('ficha_id'):
            try:
                gaes.ficha = Ficha.objects.get(pk=request.POST['ficha_id'])
            except Ficha.DoesNotExist:
                pass
        gaes.save()
        messages.success(request, 'GAES actualizado')
        return redirect('detalle_gaes', pk=pk)
    if request.user.rol == 'administrador' or request.user.is_superuser:
        fichas = Ficha.objects.all().order_by('numero')
    elif request.user.rol == 'instructor':
        fichas = Ficha.objects.filter(instructor=request.user).order_by('numero')
    else:
        fichas = Ficha.objects.none()
    return render(request, 'gaes/editar_gaes.html', {'gaes': gaes, 'fichas': fichas})


@login_required
def eliminar_gaes(request, pk):
    gaes = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes):
        return HttpResponseForbidden()
    if request.method != 'POST':
        if request.user.rol == 'instructor':
            return redirect('lista_gaes_instructor')
        return redirect('lista_gaes')
    # Auto-desvincular todo lo que bloquea el borrado antes de intentar
    Aprendiz.objects.filter(gaes=gaes).update(gaes=None)
    Competencia.objects.filter(gaes=gaes).update(gaes=None)
    desvinculadas = Ficha.objects.filter(gaes=gaes).update(gaes=None)
    try:
        gaes.delete()
        aviso = f' (se desvincularon {desvinculadas} ficha(s))' if desvinculadas else ''
        messages.success(request, f'GAES eliminado{aviso}')
    except ProtectedError:
        messages.error(request, 'No se puede eliminar el GAES. Contacte al administrador.')
    if request.user.rol == 'instructor':
        return redirect('lista_gaes_instructor')
    return redirect('lista_gaes')


@login_required
@require_POST
def agregar_aprendices_gaes(request, pk):
    gaes = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes):
        return HttpResponseForbidden()
    aprendiz_ids = request.POST.getlist('aprendiz_ids', [])
    if len(aprendiz_ids) > 4:
        messages.error(request, 'Máximo 4 aprendices por GAES')
        return redirect('detalle_gaes', pk=pk)
    if len(aprendiz_ids) < 1:
        messages.error(request, 'Debe seleccionar al menos 1 aprendiz')
        return redirect('detalle_gaes', pk=pk)
    for aprendiz_id in aprendiz_ids:
        try:
            aprendiz = Aprendiz.objects.get(pk=aprendiz_id)
            aprendiz.gaes = gaes
            aprendiz.save()
        except Aprendiz.DoesNotExist:
            pass
    messages.success(request, f'{len(aprendiz_ids)} aprendices agregados al GAES')
    return redirect('detalle_gaes', pk=pk)


@login_required
@require_POST
def eliminar_aprendiz_gaes(request, pk, aprendiz_id):
    gaes = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes):
        return HttpResponseForbidden()
    try:
        aprendiz = Aprendiz.objects.get(pk=aprendiz_id, gaes=gaes)
        aprendiz.gaes = None
        aprendiz.save()
        messages.success(request, f'{aprendiz} eliminado del GAES')
    except Aprendiz.DoesNotExist:
        messages.error(request, 'Aprendiz no encontrado en el GAES')
    return redirect('detalle_gaes', pk=pk)


@login_required
@require_POST
def transferir_aprendiz_gaes(request, pk, aprendiz_id):
    gaes_origen = get_object_or_404(GAES, pk=pk)
    if not _usuario_puede_gestionar_gaes(request.user, gaes_origen):
        return HttpResponseForbidden()
    nuevo_gaes_id = request.POST.get('nuevo_gaes_id')
    try:
        aprendiz = Aprendiz.objects.get(pk=aprendiz_id, gaes=gaes_origen)
        if nuevo_gaes_id:
            nuevo_gaes = GAES.objects.get(pk=nuevo_gaes_id)
            if nuevo_gaes.aprendices.count() >= 4:
                messages.error(request, 'El GAES destino ya tiene 4 aprendices')
                return redirect('detalle_gaes', pk=pk)
            aprendiz.gaes = nuevo_gaes
            aprendiz.save()
            messages.success(request, f'{aprendiz} transferido a {nuevo_gaes.nombre}')
        else:
            messages.error(request, 'Debe seleccionar un GAES destino')
    except (Aprendiz.DoesNotExist, GAES.DoesNotExist):
        messages.error(request, 'No se pudo transferir el aprendiz')
    return redirect('detalle_gaes', pk=pk)
