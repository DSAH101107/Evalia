# apps/trimestres/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Count
from .models import Trimestre, ResultadoAprendizaje
from apps.gaes.models import GAES
from apps.fichas.models import Ficha


@login_required
def lista_trimestres(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    trimestres = Trimestre.objects.annotate(
        cant_fichas=Count('fichas', distinct=True),
        cant_competencias=Count('competencias', distinct=True),
    ).order_by('numero')
    return render(request, 'trimestres/lista_trimestres.html', {'trimestres': trimestres})


@login_required
def crear_trimestre(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method == 'POST':
        Trimestre.objects.create(
            numero      = request.POST['numero'],
            anio        = request.POST.get('anio', timezone.now().year),
            nombre      = request.POST.get('nombre', ''),
            fecha_inicio = request.POST.get('fecha_inicio'),
            fecha_fin   = request.POST.get('fecha_fin'),
        )
        messages.success(request, 'Trimestre creado')
        return redirect('lista_trimestres')
    return render(request, 'trimestres/crear_trimestre.html')


@login_required
def detalle_trimestre(request, pk):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    trimestre = get_object_or_404(Trimestre, pk=pk)
    competencias = trimestre.competencias.select_related('ficha', 'gaes', 'fase').order_by('codigo')
    return render(request, 'trimestres/detalle_trimestre.html', {
        'trimestre': trimestre,
        'competencias': competencias,
    })


@login_required
def editar_trimestre(request, pk):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    trimestre = get_object_or_404(Trimestre, pk=pk)
    if request.method == 'POST':
        trimestre.numero = request.POST.get('numero', trimestre.numero)
        trimestre.anio  = request.POST.get('anio', trimestre.anio)
        trimestre.nombre = request.POST.get('nombre', trimestre.nombre)
        trimestre.save()
        messages.success(request, 'Trimestre actualizado')
        return redirect('detalle_trimestre', pk=pk)
    return render(request, 'trimestres/editar_trimestre.html', {'trimestre': trimestre})


@login_required
def eliminar_trimestre(request, pk):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('lista_trimestres')
    get_object_or_404(Trimestre, pk=pk).delete()
    messages.success(request, 'Trimestre eliminado')
    return redirect('lista_trimestres')
