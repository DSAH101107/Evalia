from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import models
from django.db.models import Count
from django.utils import timezone
from django.apps import apps
from .models import Competencia, Fase, Checklist, ChecklistItem
from apps.gaes.models import GAES
from apps.fichas.models import Ficha
from apps.trimestres.models import Trimestre
from apps.usuarios.models import Usuario, Rol


# ==========================================================
# FASES
# ==========================================================

@login_required
def lista_fases(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden('No tienes acceso a esta seccion')
    fases = Fase.objects.order_by('numero')
    return render(request, 'competencias/lista_fases.html', {'fases': fases})


@login_required
def crear_fase(request):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method == 'POST':
        numero = request.POST.get('numero')
        nombre = request.POST.get('nombre', '')
        try:
            fase, created = Fase.objects.get_or_create(numero=int(numero), defaults={'nombre': nombre})
            if created:
                messages.success(request, 'Fase {} creada'.format(numero))
            else:
                messages.info(request, 'Fase {} ya existe con el nombre "{}"'.format(numero, fase.nombre))
        except Exception as e:
            messages.error(request, 'Error: {}'.format(e))
        return redirect('lista_fases')
    return render(request, 'competencias/crear_fase.html')


@login_required
def editar_fase(request, pk):
    fase = get_object_or_404(Fase, pk=pk)
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method == 'POST':
        nombre = request.POST.get('nombre', fase.nombre)
        fase.nombre = nombre
        fase.save()
        messages.success(request, 'Fase {} actualizada'.format(fase.numero))
        return redirect('lista_fases')
    return render(request, 'competencias/editar_fase.html', {'fase': fase})


@login_required
def eliminar_fase(request, pk):
    if request.user.rol != 'administrador':
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('lista_fases')
    fase = get_object_or_404(Fase, pk=pk)
    numero = fase.numero
    fase.delete()
    messages.success(request, 'Fase {} eliminada'.format(numero))
    return redirect('lista_fases')


# ==========================================================
# COMPETENCIAS
# ==========================================================

COMPETENCIA_PERMISOS = ['administrador', 'instructor', 'jurado']

@login_required
def lista_competencias(request):
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return HttpResponseForbidden()
    competencias = Competencia.objects.select_related(
        'fase', 'ficha', 'trimestre'
    ).order_by('codigo')
    search = request.GET.get('search', '')
    if search:
        competencias = competencias.filter(
            models.Q(codigo__icontains=search) |
            models.Q(nombre__icontains=search) |
            models.Q(fase__nombre__icontains=search)
        )
    return render(
        request,
        'competencias/lista_competencias.html',
        {'competencias': competencias, 'search': search},
    )


@login_required
def detalle_competencia(request, pk):
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return HttpResponseForbidden()
    comp = get_object_or_404(
        Competencia.objects.select_related('fase', 'gaes', 'ficha', 'trimestre'),
        pk=pk,
    )
    return render(request, 'competencias/detalle_competencia.html', {'comp': comp})


@login_required
def crear_competencia(request):
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return HttpResponseForbidden()
    if request.method == 'POST':
        try:
            Competencia.objects.create(
                codigo=request.POST['codigo'],
                nombre=request.POST['nombre'],
                descripcion=request.POST.get('descripcion', ''),
                fase_id=request.POST.get('fase'),
                ficha_id=request.POST.get('ficha'),
                trimestre_id=request.POST.get('trimestre'),
            )
            messages.success(request, 'Competencia creada')
        except Exception as e:
            messages.error(request, 'Error: {}'.format(e))
        return redirect('lista_competencias')

    fase_preset  = request.GET.get('fase', '')
    ficha_preset = request.GET.get('ficha', '')

    ctx = {
        'fases':    Fase.objects.order_by('numero'),
        'fichas':   Ficha.objects.order_by('numero'),
        'trimestres': Trimestre.objects.order_by('numero'),
        'fase_preset':  fase_preset,
        'ficha_preset': ficha_preset,
    }
    if fase_preset:
        ctx['competencias_existentes'] = Competencia.objects.filter(
            fase_id=fase_preset, ficha_id=ficha_preset or None
        ).select_related('fase', 'gaes', 'trimestre').order_by('codigo')
    return render(request, 'competencias/crear_competencia.html', ctx)


@login_required
def editar_competencia(request, pk):
    comp = get_object_or_404(Competencia, pk=pk)
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return HttpResponseForbidden()
    if request.method == 'POST':
        comp.codigo = request.POST.get('codigo', comp.codigo)
        comp.nombre = request.POST.get('nombre', comp.nombre)
        comp.descripcion = request.POST.get('descripcion', comp.descripcion)
        for field, key in [('fase_id', 'fase'), ('ficha_id', 'ficha'), ('trimestre_id', 'trimestre')]:
            val = request.POST.get(key)
            if val:
                setattr(comp, field, val)
        comp.save()
        messages.success(request, 'Competencia actualizada')
        return redirect('detalle_competencia', pk=pk)
    ctx = {
        'comp': comp,
        'fases': Fase.objects.order_by('numero'),
        'fichas': Ficha.objects.order_by('numero'),
        'trimestres': Trimestre.objects.order_by('numero'),
    }
    return render(request, 'competencias/editar_competencia.html', ctx)


@login_required
def eliminar_competencia(request, pk):
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('lista_competencias')
    competencia = get_object_or_404(Competencia, pk=pk)
    codigo = competencia.codigo
    # Eliminar primero los ChecklistItem vinculados (PROTECT en FK)
    deleted_items = ChecklistItem.objects.filter(competencia_id=pk).count()
    ChecklistItem.objects.filter(competencia_id=pk).delete()
    competencia.delete()
    if deleted_items:
        messages.warning(
            request,
            f'Competencia {codigo} eliminada junto con {deleted_items} item(s) de lista de chequeo asociados.',
        )
    else:
        messages.success(request, f'Competencia {codigo} eliminada.')
    return redirect('lista_competencias')


# ==========================================================
# CHECKLISTS
# ==========================================================

CHECKLIST_PERMISOS = ['administrador', 'instructor', 'jurado']


@login_required
def lista_checklists(request):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    checklists = Checklist.objects.filter(activo=True).order_by('-created_at')
    search = request.GET.get('search', '')
    if search:
        checklists = checklists.filter(
            models.Q(titulo__icontains=search) |
            models.Q(descripcion__icontains=search)
        )
    return render(request, 'competencias/lista_checklists.html',
                  {'checklists': checklists, 'search': search})


@login_required
def crear_checklist(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        Checklist.objects.create(
            titulo=request.POST['titulo'],
            descripcion=request.POST.get('descripcion', ''),
        )
        messages.success(request, 'Lista de chequeo creada')
        return redirect('lista_checklists')
    return render(request, 'competencias/crear_checklist.html')


@login_required
def ver_checklist(request, pk):
    if request.user.rol not in CHECKLIST_PERMISOS:
        return HttpResponseForbidden()
    checklist = get_object_or_404(Checklist, pk=pk)
    items = checklist.items.order_by('orden')

    if request.method == 'POST':
        selected_ids = set(request.POST.getlist('competencias'))
        # Quitar items que ya no estan seleccionadas
        for item in items:
            if item.competencia_id and str(item.competencia_id) not in selected_ids:
                item.delete()
        # Agregar items nuevos
        for cid in selected_ids:
            comp = Competencia.objects.filter(id=cid).first()
            if not comp:
                continue
            exists = ChecklistItem.objects.filter(
                checklist=checklist, competencia=comp
            ).exists()
            if not exists:
                ChecklistItem.objects.create(
                    checklist=checklist,
                    competencia=comp,
                    criterio='{} - {}'.format(comp.codigo, comp.nombre),
                    descripcion='Criterios de {}'.format(comp.nombre),
                    orden=ChecklistItem.objects.filter(checklist=checklist).count(),
                )
        messages.success(request, 'Lista de chequeo actualizada')
        return redirect('ver_checklist', pk=pk)

    all_competencias = Competencia.objects.order_by('codigo')
    return render(request, 'competencias/ver_checklist.html', {
        'checklist': checklist,
        'items': items,
        'all_competencias': all_competencias,
    })


@login_required
def editar_checklist(request, pk):
    checklist = get_object_or_404(Checklist, pk=pk)
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method == 'POST':
        checklist.titulo = request.POST.get('titulo', checklist.titulo)
        checklist.descripcion = request.POST.get('descripcion', checklist.descripcion)
        checklist.save()
        messages.success(request, 'Checklist actualizada')
        return redirect('ver_checklist', pk=pk)
    return render(request, 'competencias/editar_checklist.html', {'checklist': checklist})


@login_required
def eliminar_checklist(request, pk):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()
    if request.method != 'POST':
        return redirect('lista_checklists')
    get_object_or_404(Checklist, pk=pk).delete()
    messages.success(request, 'Checklist eliminada')
    return redirect('lista_checklists')


# ==========================================================
# IMPORTAR
# ==========================================================

def _clean_text(v):
    if v is None:
        return ''
    try:
        import pandas
        if pandas.isna(v):
            return ''
    except Exception:
        pass
    return str(v).replace('\u00a0', ' ').strip()


def _parse_int(v, default=10):
    s = _clean_text(v)
    return int(float(s)) if s else default


@login_required
def importar_excel_checklists(request):
    if request.user.rol not in ['administrador', 'instructor']:
        return HttpResponseForbidden()

    fases = Fase.objects.order_by('numero')
    seleccionar_fase = request.POST.get('fase', '')

    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']

    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        archivo = request.FILES['archivo_excel']
        try:
            import pandas as pd
            df = pd.read_excel(archivo)
            df.columns = [str(c).strip().lower() for c in df.columns]

            titulo = archivo.name.replace('.xlsx', '').replace('.xls', '').title()
            checklist = Checklist.objects.create(titulo=titulo, descripcion='Importado desde Excel')

            if any(str(c).lower().startswith('unnamed') for c in df.columns):
                try:
                    df = pd.read_excel(archivo, header=16)
                    df.columns = [str(c).strip().lower() for c in df.columns]
                except Exception:
                    pass

            df.columns = [str(c).strip().lower() for c in df.columns]

            col_crit = next((c for c in ['criterio', 'criterios'] if c in df.columns), None)
            col_desc = next((c for c in df.columns if c.startswith('descrip')), None)
            col_eta  = next((c for c in ['etapa'] if c in df.columns), None)
            col_punt = next((c for c in df.columns if 'puntaje' in c and 'max' in c), None)

            if not col_crit or not col_desc:
                item_col = next((c for c in df.columns if 'item' in c), None)
                indic_col = next((c for c in df.columns if 'indicador' in c), None)
                obs_col = next((c for c in df.columns if 'observ' in c), None)
                if not col_crit and indic_col:
                    col_crit = indic_col
                if not col_desc and obs_col:
                    col_desc = obs_col

            if not col_crit or not col_desc:
                raise ValueError('No se detectaron columnas de criterio/descripcion')

            created = 0
            for _, row in df.iterrows():
                criterio = _clean_text(row.get(col_crit, ''))
                descripcion = _clean_text(row.get(col_desc, ''))
                etapa = _clean_text(row.get(col_eta, '')) if col_eta else str(seleccionar_fase)
                puntaje = _parse_int(row.get(col_punt, ''), 10) if col_punt else 10
                if not criterio:
                    continue
                ChecklistItem.objects.create(
                    checklist=checklist,
                    criterio=criterio,
                    descripcion=descripcion,
                    etapa=etapa,
                    puntaje_maximo=puntaje,
                    orden=created,
                )
                created += 1
            messages.success(request, 'Checklist "{}" creado con {} items'.format(titulo, created))
        except Exception as e:
            messages.error(request, str(e))
        return redirect('lista_checklists')
    return render(request, 'competencias/importar_excel_checklists.html', {'fases': fases})


# ─────────────────────────────────────────
# API  – Competencias por Fase + Ficha
# ─────────────────────────────────────────

@login_required
def api_competencias_por_fase_ficha(request):
    """Devuelve las competencias filtradas por fase y opcionalmente por ficha."""
    if request.user.rol not in COMPETENCIA_PERMISOS:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    fase_id   = request.GET.get('fase')
    ficha_id  = request.GET.get('ficha', '')

    qs = Competencia.objects.select_related('fase').filter(fase_id=fase_id).order_by('codigo')
    if ficha_id:
        qs = qs.filter(ficha_id=ficha_id)

    data = [
        {
            'id':    c.id,
            'codigo': c.codigo,
            'nombre': c.nombre,
            'fase':  c.fase.numero,
            'activo': c.activo,
        }
        for c in qs
    ]
    return JsonResponse({'competencias': data})
