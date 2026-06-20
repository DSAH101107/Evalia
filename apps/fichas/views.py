from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Count
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import json
from .models import Ficha
from apps.evaluacion.models import Trimestre, Aprendiz, GAES
from apps.usuarios.models import Usuario

@login_required
def lista_fichas(request):
    """Lista básica de fichas con filtros."""
    from django.db.models import Q
    from apps.evaluacion.models import GAES
    
    fichas = Ficha.objects.all().order_by('numero')
    
    # Filtros multicriterio
    filtro_numero = request.GET.get('filtro_numero', '')
    filtro_programa = request.GET.get('filtro_programa', '')
    filtro_jornada = request.GET.get('filtro_jornada', '')
    filtro_gaes = request.GET.get('filtro_gaes', '')
    filtro_instructor = request.GET.get('filtro_instructor', '')
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
    if filtro_jornada:
        fichas = fichas.filter(jornada=filtro_jornada)
    if filtro_gaes:
        fichas = fichas.filter(gaes__nombre=filtro_gaes)
    if filtro_instructor:
        fichas = fichas.filter(instructor__username__icontains=filtro_instructor)
    
    # Opciones para dropdowns
    gaes_list = GAES.objects.all().order_by('nombre')
    instructores_list = Usuario.objects.filter(rol='instructor').order_by('username')
    
    return render(request, 'fichas/lista_fichas.html', {
        'fichas': fichas,
        'filtro_numero': filtro_numero,
        'filtro_programa': filtro_programa,
        'filtro_jornada': filtro_jornada,
        'filtro_gaes': filtro_gaes,
        'filtro_instructor': filtro_instructor,
        'search': search,
        'gaes_list': gaes_list,
        'instructores_list': instructores_list,
    })

@login_required
def lista_fichas_con_aprendices(request):
    """Lista de fichas con el conteo de aprendices para cada una (solo para administradores)."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    fichas = Ficha.objects.annotate(
        num_aprendices=Count('aprendices', distinct=True)
    ).order_by('numero')
    
    return render(request, 'fichas/lista_fichas_con_aprendices.html', {
        'fichas': fichas
    })

@login_required
def ver_gaes_ficha(request, ficha_id):
    """Muestra los GAES que tienen aprendices en una ficha específica."""
    ficha = get_object_or_404(Ficha, id=ficha_id)
    if request.user.rol != 'administrador':
        if ficha.instructor != request.user:
            return HttpResponseForbidden('No tienes acceso a esta sección')
    
    gaes_con_aprendices = GAES.objects.filter(
        ficha=ficha
    ).annotate(
        cant_aprendices=Count('aprendices', distinct=True)
    ).filter(cant_aprendices__gt=0).order_by('nombre')
    
    gaes_list = []
    for gaes in gaes_con_aprendices:
        aprendices = Aprendiz.objects.filter(gaes=gaes).select_related('ficha', 'gaes', 'fase')
        gaes_list.append({
            'gaes': gaes,
            'aprendices': aprendices,
            'cant_aprendices': aprendices.count()
        })
    
    return render(request, 'fichas/ver_gaes_ficha.html', {
        'ficha': ficha,
        'gaes_list': gaes_list,
    })

@login_required
def aprendices_por_ficha(request, ficha_id):
    """Lista de aprendices pertenecientes a una ficha específica (solo para administradores)."""
    print(f"DEBUG: aprendices_por_ficha called with ficha_id={ficha_id}, user={request.user}, rol={getattr(request.user, 'rol', 'No rol')}")
    
    if request.user.rol != 'administrador':
        print(f"DEBUG: Permission denied. User rol is {request.user.rol}")
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    print(f"DEBUG: Found ficha: {ficha}")
    
    # Let's also check what's in the database directly
    all_aprendices = Aprendiz.objects.all()
    print(f"DEBUG: Total aprendices in DB: {all_aprendices.count()}")
    
    aprendices_with_ficha = Aprendiz.objects.filter(ficha__isnull=False)
    print(f"DEBUG: Aprendices with ficha set: {aprendices_with_ficha.count()}")
    
    aprendices_for_this_ficha = Aprendiz.objects.filter(ficha=ficha)
    print(f"DEBUG: Aprendices for ficha {ficha.id}: {aprendices_for_this_ficha.count()}")
    
    for i, aprendiz in enumerate(aprendices_for_this_ficha):
        print(f"DEBUG: Aprendiz {i+1}: {aprendiz.nombres} {aprendiz.apellidos}, ficha={aprendiz.ficha}")
    
    aprendices = Aprendiz.objects.filter(ficha=ficha).select_related('ficha', 'gaes', 'fase', 'usuario')
    print(f"DEBUG: Query returned {aprendices.count()} aprendices")
    
    for i, aprendiz in enumerate(aprendices):
        print(f"DEBUG: Aprendiz {i+1}: {aprendiz.nombres} {aprendiz.apellidos}, ficha={aprendiz.ficha}")
    
    # Also add to context for debugging in template
    context = {
        'ficha': ficha,
        'aprendices': aprendices,
        'debug_count': aprendices.count()
    }
    
    print(f"DEBUG: Rendering template with context")
    return render(request, 'fichas/aprendices_por_ficha.html', context)

@login_required
def crear_ficha(request):
    """Crear una nueva ficha."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    if request.method == 'POST':
        numero = request.POST.get('numero', '').strip()
        programa = request.POST.get('programa', '').strip()
        jornada = request.POST.get('jornada', 'mañana')
        gaes_cantidad = request.POST.get('gaes_cantidad', '1')
        trimestre_id = request.POST.get('trimestre')
        instructor_id = request.POST.get('instructor')
        
        if not numero:
            messages.error(request, 'El número de ficha es requerido.')
            return redirect('crear_ficha')
        
        if Ficha.objects.filter(numero=numero).exists():
            messages.error(request, f'Ya existe una ficha con el número {numero}.')
            return redirect('crear_ficha')
        
        try:
            gaes_cantidad = int(gaes_cantidad)
            if gaes_cantidad < 1 or gaes_cantidad > 10:
                raise ValueError()
        except ValueError:
            messages.error(request, 'La cantidad de GAES debe estar entre 1 y 10.')
            return redirect('crear_ficha')
        
        trimestre = None
        if trimestre_id:
            try:
                trimestre = Trimestre.objects.get(id=trimestre_id)
            except Trimestre.DoesNotExist:
                pass
        
        instructor = None
        if instructor_id:
            try:
                instructor = Usuario.objects.get(id=instructor_id, rol='instructor')
            except Usuario.DoesNotExist:
                pass
        
        ficha = Ficha.objects.create(
            numero=numero,
            programa=programa,
            jornada=jornada,
            trimestre=trimestre,
            instructor=instructor,
            estado='activo'
        )
        
        gaes_creadas = []
        for i in range(gaes_cantidad):
            gaes = GAES.objects.create(
                nombre=f"GAES {i+1:02d} de {numero}",
                descripcion=f"GAES generada automáticamente para la ficha {numero}",
                ficha=ficha,
                activo=True
            )
            gaes_creadas.append(gaes)
        
        if gaes_creadas:
            ficha.gaes = gaes_creadas[0]
            ficha.save()
        
        messages.success(
            request, 
            f'Ficha {numero} creada exitosamente con {gaes_cantidad} GAES.'
        )
        return redirect('detalle_ficha', pk=ficha.pk)
    
    else:
        trimestres = Trimestre.objects.filter(activo=True).order_by('-anio', 'numero')
        instructores = Usuario.objects.filter(rol='instructor').order_by('username')
        
        last_ficha = Ficha.objects.order_by('-numero').first()
        next_ficha_num = int(last_ficha.numero) + 1 if last_ficha and last_ficha.numero.isdigit() else 1
        next_ficha = str(next_ficha_num).zfill(5)
        
        return render(request, 'fichas/crear_ficha.html', {
            'trimestres': trimestres,
            'instructores': instructores,
            'next_ficha': next_ficha
        })

@login_required
def detalle_ficha(request, pk):
    """Detalle de una ficha."""
    ficha = get_object_or_404(Ficha, pk=pk)
    return render(request, 'fichas/detalle_ficha.html', {
        'ficha': ficha
    })

@login_required
def editar_ficha(request, pk):
    """Editar una ficha existente."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    ficha = get_object_or_404(Ficha, pk=pk)
    if request.method == 'POST':
        numero = request.POST.get('numero', '').strip()
        programa = request.POST.get('programa', '').strip()
        jornada = request.POST.get('jornada', 'mañana')
        gaes_id = request.POST.get('gaes')
        trimestre_id = request.POST.get('trimestre')
        instructor_id = request.POST.get('instructor')
        
        if not numero:
            messages.error(request, 'El número de ficha es requerido.')
            return redirect('editar_ficha', pk=pk)
        
        if Ficha.objects.filter(numero=numero).exclude(pk=pk).exists():
            messages.error(request, f'Ya existe otra ficha con el número {numero}.')
            return redirect('editar_ficha', pk=pk)
        
        gaes = None
        if gaes_id:
            try:
                gaes = GAES.objects.get(id=gaes_id)
            except GAES.DoesNotExist:
                pass
        
        trimestre = None
        if trimestre_id:
            try:
                trimestre = Trimestre.objects.get(id=trimestre_id)
            except Trimestre.DoesNotExist:
                pass
        
        instructor = None
        if instructor_id:
            try:
                instructor = Usuario.objects.get(id=instructor_id, rol='instructor')
            except Usuario.DoesNotExist:
                pass
        
        ficha.numero = numero
        ficha.programa = programa
        ficha.jornada = jornada
        ficha.gaes = gaes
        ficha.trimestre = trimestre
        ficha.instructor = instructor
        ficha.save()
        
        messages.success(request, f'Ficha {numero} actualizada exitosamente.')
        return redirect('detalle_ficha', pk=pk)
    else:
        trimestres = Trimestre.objects.filter(activo=True).order_by('-anio', 'numero')
        gaes_qs = GAES.objects.all().order_by('nombre')
        instructores = Usuario.objects.filter(rol='instructor').order_by('username')
        
        return render(request, 'fichas/editar_ficha.html', {
            'ficha': ficha,
            'trimestres': trimestres,
            'gaes': gaes_qs,
            'instructores': instructores
        })

@login_required
def eliminar_ficha(request, pk):
    """Eliminar una ficha."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')

    ficha = get_object_or_404(Ficha, pk=pk)
    if request.method == 'POST':
        ficha.delete()
        messages.success(request, 'Ficha eliminada exitosamente.')
        return redirect('lista_fichas')
    return render(request, 'fichas/eliminar_ficha.html', {
        'ficha': ficha
    })

@login_required
def actualizar_gaes_ficha(request, pk):
    """Actualizar los GAES de una ficha."""
    if request.user.rol != 'administrador':
        return HttpResponseForbidden('No tienes acceso a esta sección')
    
    ficha = get_object_or_404(Ficha, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'cambiar_principal':
            gaes_id = request.POST.get('gaes_principal')
            if gaes_id:
                try:
                    gaes = GAES.objects.get(id=gaes_id, ficha=ficha)
                    ficha.gaes = gaes
                    ficha.save()
                    messages.success(request, 'GAES principal actualizada exitosamente.')
                except GAES.DoesNotExist:
                    messages.error(request, 'GAES no válida para esta ficha.')
            else:
                ficha.gaes = None
                ficha.save()
                messages.success(request, 'GAES principal eliminada.')
            return redirect('actualizar_gaes_ficha', pk=pk)
            
        elif accion == 'crear_gaes':
            nombre = request.POST.get('nombre_gaes', '').strip()
            descripcion = request.POST.get('descripcion_gaes', '').strip()
            
            if nombre:
                gaes = GAES.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    ficha=ficha,
                    activo=True
                )
                messages.success(request, f'GAES "{nombre}" creada exitosamente.')
            else:
                messages.error(request, 'El nombre de la GAES es requerido.')
            return redirect('actualizar_gaes_ficha', pk=pk)
    
    gaes_list = GAES.objects.filter(ficha=ficha).order_by('nombre')
    
    return render(request, 'fichas/actualizar_gaes_ficha.html', {
        'ficha': ficha,
        'gaes_list': gaes_list
    })

@login_required
def api_gaes_por_ficha(request, pk):
    """API para obtener los GAES de una ficha que tienen aprendices asignados."""
    ficha = get_object_or_404(Ficha, pk=pk)
    # Get all GAES that belong to this ficha (through the grupos relationship)
    # and have at least one apprentice assigned to them
    gaes_qs = GAES.objects.filter(
        ficha=ficha
    ).filter(
        aprendices__isnull=False
    ).distinct().order_by('nombre')
    
    gaes_data = []
    for gaes in gaes_qs:
        gaes_data.append({
            'id': gaes.id,
            'nombre': gaes.nombre,
            'descripcion': gaes.descripcion
        })
    
    return JsonResponse({'gaes': gaes_data})

@login_required
def api_integrantes_gaes(request, pk):
    """API para obtener los integrantes de un GAES."""
    gaes = get_object_or_404(GAES, pk=pk)
    # Get all apprentices that belong to this GAES
    aprendices = Aprendiz.objects.filter(
        gaes=gaes
    ).select_related('ficha', 'fase', 'usuario').order_by('nombres', 'apellidos')
    
    integrantes_data = []
    for aprendiz in aprendices:
        integrantes_data.append({
            'id': aprendiz.id,
            'nombres': aprendiz.nombres,
            'apellidos': aprendiz.apellidos,
            'documento': aprendiz.documento,
            'ficha_numero': aprendiz.ficha.numero if aprendiz.ficha else None,
            'ficha_programa': aprendiz.ficha.programa if aprendiz.ficha else None
        })
    
    return JsonResponse({'integrantes': integrantes_data})


@login_required
def lista_gaes_con_aprendices(request):
    if request.user.rol not in ['administrador', 'instructor', 'jurado']:
        return HttpResponseForbidden('No tienes acceso a esta sección')
    gaes_qs = GAES.objects.filter(aprendices__isnull=False).distinct().annotate(
        cant_aprendices=Count('aprendices'),
        cant_fichas=Count('fichas', distinct=True)
    ).order_by('nombre')
    if request.user.rol == 'instructor':
        gaes_qs = gaes_qs.filter(fichas__instructor=request.user).distinct()
    return render(request, 'fichas/lista_gaes_con_aprendices.html', {
        'gaes_list': gaes_qs
    })