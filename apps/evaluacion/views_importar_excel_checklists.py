import unicodedata
import re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse

import pandas as pd

from .models import Checklist, ChecklistItem


def _normalize_string(s):
    if s is None:
        return ''
    s = str(s)
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return s.strip().lower()



@login_required
def importar_excel_checklists(request):
    if request.user.rol not in ['administrador', 'instructor']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No tienes acceso a esta sección'}, status=403)
        return HttpResponseForbidden('No tienes acceso a esta sección')

    if request.method == 'GET':
        return render(request, 'evaluacion/importar_excel_checklists.html')

    if 'archivo_excel' not in request.FILES:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'No se subió archivo Excel'}, status=400)
        messages.error(request, 'No se subió archivo Excel')
        return redirect('importar_excel_checklists_evaluacion')

    if pd is None:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': "pandas no está instalado. Instala con: pip install pandas openpyxl"}, status=500)
        messages.error(request, "pandas no está instalado. Instala con: pip install pandas openpyxl")
        return redirect('importar_excel_checklists_evaluacion')

    archivo = request.FILES['archivo_excel']

    try:
        df = None
        last_exception = None

        try:
            archivo.seek(0)
            df = pd.read_excel(archivo)
        except Exception as e:
            last_exception = e

        if df is None:
            raise last_exception if last_exception else ValueError("No se pudo leer el archivo Excel")

        df.columns = [_normalize_string(c) for c in df.columns]

        def _pick_col(*names):
            for n in names:
                for col in df.columns:
                    if n in col:
                        return col
            return None

        def _is_valid_value(val):
            if pd.isna(val):
                return False
            s = _normalize_string(val)
            return s not in ['', 'nan', 'none', 'null', '*']

        def _detect_first_data_col():
            for col in df.columns:
                for val in df[col]:
                    if _is_valid_value(val):
                        return col
            return None

        def _detect_por_contenido():
            indicator_keywords = ['criterio', 'criterios', 'indicadores', 'variables', 'item', 'items']

            best_col = None
            best_header_row = None
            best_valid_count = -1

            for row_idx in range(min(25, len(df))):
                for col in df.columns:
                    val = df.at[row_idx, col]
                    if not _is_valid_value(val):
                        continue
                    s = _normalize_string(val)
                    matched = any(kw in s for kw in indicator_keywords)
                    if not matched:
                        continue

                    valid_below = 0
                    for r_idx in range(row_idx + 1, min(row_idx + 20, len(df))):
                        v = df.at[r_idx, col]
                        if not _is_valid_value(v):
                            continue
                        sv = str(v).strip()
                        if len(sv) >= 20 and not re.match(r'^[\d\s]+(\.|-)', sv):
                            valid_below += 1

                    if valid_below > best_valid_count:
                        best_valid_count = valid_below
                        best_col = col
                        best_header_row = row_idx

            if best_col is not None and best_valid_count > 0:
                return best_col

            col_idx_candidates = ['unnamed: 3', 'unnamed: 2', 'unnamed: 4']
            for cname in col_idx_candidates:
                if cname in df.columns:
                    return cname
            return None

        def _es_criterio_valido(text):
            if not text:
                return False
            s = str(text).strip()

            if len(s) < 30:
                return False

            s_norm = unicodedata.normalize('NFD', s).lower()

            keywords_basura = [
                'servicio nacional de aprendizaje',
                'regional distrito capital',
                'centro de servicios financieros',
                'instrumento para valorar',
                'sistema integrado de gestion',
                'proceso gestion de la formacion profesional integral',
                'procedimiento ejecucion de la formacion profesional integral',
                'nombre y codigo del programa',
                'tecno logo en',
                'resultado de aprendizaje',
                'indicadores de trabajo en equipo scrum',
                'recomendaciones',
                'juicio de valor',
                'firma jurado evaluador',
                'nelson hernan rodriguez',
                'javier leonardo pineda',
                'lista de verificacion',
                'este instrumento tiene como objetivo',
                'nombres de los aprendices',
                'nombre del instructor',
                'nombre y codigo del programa',
                'nombre del proyecto',
                'nombre de los',
                'duracion de evaluacion',
                'fecha de aplicacion',
                'no. de ficha',
                'informacion general',
            ]

            for kw in keywords_basura:
                if kw in s_norm:
                    return False

            header_patterns = [
                r'^indicadores?\s*(y/o)?\s*variables?$',
                r'^criterios?\s*:?\s*$',
                r'^items?\s*:?\s*$',
                r'^indicadores?\s*$',
                r'^variables?\s*$',
                r'^\d+\.\d+\s*criterio',
                r'^etapa\s*\d*',
                r'^fase\s*\d*',
                r'^competencia\s',
                r'^resultado\s+de\s+aprendizaje',
                r'^producto\s*:\s*$',
            ]
            for pat in header_patterns:
                if re.search(pat, s_norm):
                    return False

            if s.count('\n') > 5:
                return False

            if re.match(r'^[\d\s]+(\.|-)', s) and len(s.strip()) < 60:
                return False

            if ':' in s:
                parts = s.split(':', 1)
                if len(parts[0].strip()) < 5 and len(parts[1].strip()) < 5:
                    return False

            return True

        col_criterio = _pick_col('criterio', 'criterios', 'indicadores', 'variables', 'item')
        if not col_criterio:
            col_criterio = _detect_por_contenido()

        col_etapa = _pick_col('etapa')
        col_puntaje = _pick_col('puntaje_maximo', 'puntaje')
        col_observaciones = _pick_col('observaciones', 'observacion', 'comentario', 'comentarios', 'descripcion_item', 'descripcion', 'desc')

        if not col_criterio:
            cols_str = " | ".join(str(c) for c in df.columns)
            msg = f'Falta columna obligatoria (criterio/indicadores/variables/item). Columnas detectadas: [{cols_str}]'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
        return redirect('importar_excel_checklists_evaluacion')

        titulo = request.POST.get('titulo', '').strip() or 'Checklist importado'
        descripcion = request.POST.get('descripcion', '').strip() or 'Importado desde Excel'

        checklist = Checklist.objects.create(titulo=titulo, descripcion=descripcion, activo=True)

        created_items = 0
        errores = []

        for idx, row in df.iterrows():
            fila_num = idx + 2
            try:
                raw_criterio = row.get(col_criterio)
                if not _is_valid_value(raw_criterio):
                    continue

                criterio = str(raw_criterio).strip()
                if not _es_criterio_valido(criterio):
                    continue

                raw_etapa = row.get(col_etapa)
                etapa = str(raw_etapa).strip() if _is_valid_value(raw_etapa) else ''

                raw_obs = row.get(col_observaciones)
                observaciones = str(raw_obs).strip() if _is_valid_value(raw_obs) else ''

                puntaje_maximo = 10
                if col_puntaje:
                    raw_puntaje = row.get(col_puntaje)
                    if _is_valid_value(raw_puntaje):
                        try:
                            puntaje_maximo = int(float(raw_puntaje))
                        except (ValueError, TypeError):
                            pass

                ChecklistItem.objects.create(
                    checklist=checklist,
                    competencia=None,
                    criterio=criterio,
                    descripcion=observaciones,
                    puntaje_maximo=puntaje_maximo,
                    orden=len(checklist.items.all()),
                    etapa=etapa,
                )
                created_items += 1

            except Exception as e:
                errores.append(f'Fila {fila_num}: {str(e)}')

        if errores:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Importación finalizó con errores.\n' + '\n'.join(errores[:10])}, status=400)
            messages.warning(request, 'Importación finalizó con errores.\n' + '\n'.join(errores[:10]))

        messages.success(request, f'Se crearon {created_items} items en el checklist "{checklist.titulo}".')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Se crearon {created_items} items.',
                'redirect': '/evaluacion/checklists/'
            })
        return redirect('lista_checklists_evaluacion')

    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': f'Error al procesar el archivo: {str(e)}'}, status=500)
        messages.error(request, f'Error al procesar el archivo: {str(e)}')
        return redirect('importar_excel_checklists_evaluacion')
