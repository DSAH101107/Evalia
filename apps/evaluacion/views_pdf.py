from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from .models import Aprendiz, Checklist, ChecklistItem, Fase, GAES, Ficha
from apps.usuarios.models import Usuario, Rol

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

import pdfplumber
import pandas as pd
from io import BytesIO


@login_required
def importar_pdf_aprendices(request):
    if request.method == 'GET':
        fichas_list = Ficha.objects.order_by('numero')
        return render(request, 'evaluacion/importar_pdf_aprendices.html', {
            'fichas_list': fichas_list,
            'fase_choices': [str(f) for f in Fase.objects.order_by('numero').values_list('numero', flat=True)],
        })

    if request.user.rol not in ['administrador', 'instructor']:
        messages.error(request, 'No tienes acceso')
        return redirect('lista_aprendices')

    if 'archivo_pdf' not in request.FILES:
        messages.error(request, 'No se subió archivo PDF')
        return redirect('importar_pdf_aprendices')

    archivo = request.FILES['archivo_pdf']
    created = 0
    updated = 0

    try:
        logger.info("Iniciando importacion PDF de aprendices")
        with pdfplumber.open(BytesIO(archivo.read())) as pdf:
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

        logger.info("Tablas extraidas: %d paginas", len(all_tables))

        if not all_tables:
            logger.warning("No se encontraron tablas en el PDF")
            messages.error(request, 'No se encontraron tablas en el PDF')
            return redirect('lista_aprendices')

        df = pd.DataFrame(all_tables[0][1:], columns=all_tables[0][0])
        logger.info("DataFrame creado con %d filas y columnas: %s", len(df), list(df.columns))

        def _norm_col(s: str) -> str:
            s = '' if s is None else str(s)
            s = s.strip().lower()
            s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            s = s.replace('ñ', 'n')
            s = re.sub(r'\s+', ' ', s)
            return s

        col_map = {_norm_col(c): c for c in df.columns}
        logger.debug("Mapeo de columnas normalizadas: %s", col_map)

        def pick_col(*candidates):
            for cand in candidates:
                key = _norm_col(cand)
                if key in col_map:
                    return col_map[key]
                for k, orig in col_map.items():
                    if key and key in k:
                        return orig
            return None

        col_nombre = pick_col('nombre', 'nombres')
        col_apellido = pick_col('apellido', 'apellidos')
        col_programa = pick_col('programa de formacion', 'programa de formacion', 'programa')
        col_ficha = pick_col('ficha')
        col_trimestre = pick_col('trimestre')

        logger.debug("Columnas detectadas -> nombre: %s, apellido: %s, programa: %s, ficha: %s, trimestre: %s",
                     col_nombre, col_apellido, col_programa, col_ficha, col_trimestre)

        default_fase_id = request.POST.get('default_fase', '').strip()
        default_ficha_val = request.POST.get('default_ficha', '').strip()

        for i, (_, row) in enumerate(df.iterrows()):
            nombre = str(row.get(col_nombre, '')).strip() if col_nombre else ''
            apellido = str(row.get(col_apellido, '')).strip() if col_apellido else ''
            programa = str(row.get(col_programa, '')).strip() if col_programa else ''
            ficha_val = str(row.get(col_ficha, '')).strip() if col_ficha else ''
            trimestre = str(row.get(col_trimestre, '')).strip() if col_trimestre else ''

            logger.debug("Fila %d -> nombre='%s', apellido='%s', ficha='%s'", i, nombre, apellido, ficha_val)

            if not (nombre and apellido and ficha_val):
                logger.warning("Fila %d saltada: faltan campos obligatorios (nombre='%s', apellido='%s', ficha='%s')",
                               i, nombre, apellido, ficha_val)
                continue

            documento = f"{nombre[:4].upper()}{apellido[:4].upper()}{ficha_val}"
            documento = re.sub(r'[^A-Za-z0-9]', '', documento)[:20]
            logger.debug("Fila %d -> documento generado: '%s'", i, documento)

            # Get or create ficha_obj (from PDF or default)
            ficha_obj = None
            if ficha_val:
                ficha_obj, _ = Ficha.objects.get_or_create(numero=ficha_val)
            elif default_ficha_val:
                ficha_obj, _ = Ficha.objects.get_or_create(numero=default_ficha_val)

            # No asignar GAES automáticamente - el instructor lo hará después
            gaes_obj = None

            fase_obj = None
            if default_fase_id:
                fase_obj = Fase.objects.filter(numero=default_fase_id).first()
                if fase_obj:
                    logger.debug("Fila %d -> Fase default usada: %s (id=%s)", i, default_fase_id, fase_obj.id)
                else:
                    logger.warning("Fila %d -> Fase default '%s' no encontrada en BD", i, default_fase_id)

            # Asignar propietario solo si el usuario es instructor
            propietario = request.user if request.user.rol == 'instructor' else None

            aprendiz_defaults = {
                'nombres': nombre,
                'apellidos': apellido,
                'programa': programa,
                'gaes': gaes_obj,
                'ficha': ficha_obj,
                'fase': fase_obj,
                'trimestre': trimestre if trimestre else '',
                'email': f"{nombre.lower()}.{apellido.lower()}@sena.edu.co",
                'telefono': '',
            }

            aprendiz, created_new = Aprendiz.objects.update_or_create(
                documento=documento,
                defaults=aprendiz_defaults,
            )
            
            if propietario and not aprendiz.propietario:
                aprendiz.propietario = propietario
                aprendiz.save(update_fields=['propietario'])
                logger.debug("Fila %d -> Propietario asignado: usuario_id=%s", i, propietario.id)

            logger.info("Fila %d -> Aprendiz %s (documento='%s', id=%d, fase_id=%s)",
                        i, 'CREADO' if created_new else 'ACTUALIZADO', documento, aprendiz.id,
                        aprendiz.fase_id)

            username = documento
            temp_password = 'aprendiz123'

            usuario, created_usuario = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'email': f"{nombre.lower()}.{apellido.lower()}@sena.edu.co",
                    'rol': Rol.APRENDIZ,
                }
            )

            if created_usuario:
                usuario.set_password(temp_password)
                usuario.save()
                aprendiz.usuario = usuario
                aprendiz.save()
                logger.info("Fila %d -> Usuario creado: username='%s' (id=%d)", i, username, usuario.id)
            else:
                logger.debug("Fila %d -> Usuario ya existia: username='%s' (id=%d)", i, username, usuario.id)

            if created_new:
                created += 1
            else:
                updated += 1

        logger.info("Importacion PDF completada: %d creados, %d actualizados", created, updated)
        messages.success(request, f'Importados: {created} nuevos, {updated} actualizados')

    except Exception as e:
        logger.error("Error en importacion PDF: %s", str(e), exc_info=True)
        messages.error(request, f'Error: {str(e)}')

    return redirect('lista_aprendices')


@login_required
def importar_pdf_aprendices_form(request):
    return render(request, 'evaluacion/importar_pdf_aprendices.html')


@login_required
def importar_pdf_checklists(request):
    if request.user.rol not in ['administrador', 'instructor']:
        messages.error(request, 'No tienes acceso')
        return redirect('lista_checklists')

    if request.method == 'GET':
        return render(request, 'evaluacion/importar_pdf_checklists.html')

    if 'archivo_pdf' not in request.FILES:
        messages.error(request, 'No se subió archivo PDF')
        return redirect('importar_pdf_checklists')

    archivo = request.FILES['archivo_pdf']

    def _normalize(s):
        if s is None:
            return ''
        s = str(s)
        s = ''.join(c for c in unicodedata.normalize('NFD', s)
                    if unicodedata.category(c) != 'Mn')
        s = re.sub(r'\s+', ' ', s).strip().lower()
        return s

    def _clean_text(value):
        if value is None:
            return ''
        s = str(value).strip()
        s = s.replace('\r', ' ').replace('\n', ' ')
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _is_empty(value):
        if value is None:
            return True
        if pd.isna(value):
            return True
        s = _normalize(value)
        return s in ['', 'nan', 'none', 'null', '*', '-']

    def _is_boilerplate(value):
        s_norm = _normalize(value)
        if not s_norm:
            return True
        boilerplate = [
            'servicio nacional de aprendizaje',
            'sistema integrado de gestion',
            'proceso gestion de la formacion profesional integral',
            'instrumento para valorar',
            'lista de chequeo',
            'lista de verificacion',
            'resultado de aprendizaje',
            'evidencia de aprendizaje',
            'criterios de evaluacion',
            'nombre y codigo del programa',
            'nombre del instructor',
            'nombre de los aprendices',
            'fecha de aplicacion',
            'duracion de evaluacion',
            'firma jurado evaluador',
            'juicio de valor',
            'recomendaciones',
            'observaciones generales',
            'sena regional',
            'centro de formacion',
            'codigo del programa',
            'nombre del proyecto',
            'no. de ficha',
            'informacion general',
        ]
        if any(kw in s_norm for kw in boilerplate):
            return True
        header_patterns = [
            r'^criterios?\s*:?\s*$',
            r'^indicadores?\s*(y/o)?\s*variables?$',
            r'^items?\s*:?\s*$',
            r'^etapa\s*\d*$',
            r'^fase\s*\d*$',
            r'^competencia\s',
            r'^producto\s*:\s*$',
            r'^observaciones?\s*:?\s*$',
            r'^comentarios?\s*:?\s*$',
        ]
        return any(re.search(pat, s_norm) for pat in header_patterns)

    def _is_header_keyword(value):
        s_norm = _normalize(value)
        return any(kw in s_norm for kw in [
            'criterio', 'criterios', 'indicador', 'indicadores',
            'variable', 'variables', 'item', 'items'
        ])

    def _pad_row(row, width):
        row = list(row) if row else []
        return row + [None] * (width - len(row))

    def _unique_columns(header):
        seen = {}
        columns = []
        for h in header:
            base = _normalize(h) or 'columna'
            seen[base] = seen.get(base, 0) + 1
            columns.append(f'{base}_{seen[base]}' if seen[base] > 1 else base)
        return columns

    def _rows_to_dataframe(rows, header_row):
        max_cols = max([len(header_row)] + [len(r) for r in rows])
        columns = _unique_columns(_pad_row(header_row, max_cols))
        data = []
        for row in rows:
            if all(_is_empty(c) for c in row):
                continue
            row_norm = [_normalize(c) for c in row]
            if any(_is_header_keyword(c) for c in row_norm) and sum(1 for c in row_norm if c) <= 2:
                continue
            data.append(_pad_row(row, max_cols))
        if not data:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data, columns=columns)

    def _score_header(row):
        norms = [_normalize(c) for c in row]
        if not any(norms):
            return 0
        score = 0
        if any('criterio' in n or 'indicador' in n or 'variable' in n or 'item' in n for n in norms):
            score += 10
        score += sum(1 for n in norms if 'criterio' in n or 'indicador' in n or 'variable' in n)
        score += sum(0.5 for n in norms if 'etapa' in n or 'fase' in n)
        score += sum(0.25 for n in norms if 'comentario' in n or 'descripcion' in n or 'observacion' in n or 'puntaje' in n)
        return score

    def _extract_tables(archivo_pdf):
        archivo_pdf.seek(0)
        table_settings = {
            'vertical_strategy': 'text',
            'horizontal_strategy': 'text',
            'snap_tolerance': 3,
            'join_tolerance': 3,
            'intersection_tolerance': 5,
            'min_words_per_line': 1,
        }
        extracted = []
        with pdfplumber.open(BytesIO(archivo_pdf.read())) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    tables = page.extract_tables(table_settings=table_settings)
                except TypeError:
                    tables = page.extract_tables()
                for table_number, table in enumerate(tables, start=1):
                    if table:
                        extracted.append((page_number, table_number, table))
        return extracted

    def _detect_dataframe_from_tables(archivo_pdf):
        tables = _extract_tables(archivo_pdf)
        best = None
        best_score = -1
        best_source = ''
        best_columns = ''

        for page_number, table_number, table in tables:
            if not table or len(table) < 2:
                continue
            for row_idx in range(min(8, len(table))):
                header_row = table[row_idx]
                score = _score_header(header_row)
                if score <= 0:
                    continue
                rows_below = table[row_idx + 1:]
                valid_below = sum(1 for r in rows_below[:25] if any(not _is_empty(c) for c in r))
                score += min(valid_below, 20) * 0.05
                if score > best_score:
                    best_score = score
                    best = (table, row_idx)
                    best_source = f'página {page_number}, tabla {table_number}, fila {row_idx + 1}'
                    best_columns = ', '.join(str(c) for c in header_row if not _is_empty(c))

        if not best:
            return None, '', ''

        table, row_idx = best
        df = _rows_to_dataframe(table[row_idx + 1:], table[row_idx])
        return df, best_source, best_columns

    def _extract_text(archivo_pdf):
        archivo_pdf.seek(0)
        chunks = []
        with pdfplumber.open(BytesIO(archivo_pdf.read())) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text(x_tolerance=1, y_tolerance=3)
                except TypeError:
                    text = page.extract_text()
                if text:
                    chunks.append(text)
        return '\n'.join(chunks)

    def _parse_text_candidates(text):
        rows = []
        in_criterio_section = False
        stop_keywords = [
            'observaciones generales', 'firma', 'juicio de valor', 'recomendaciones',
            'nombre del aprendiz', 'nombre del instructor', 'informacion general',
            'codigo del programa', 'nombre y codigo del programa'
        ]
        for raw_line in text.splitlines():
            line = _clean_text(raw_line)
            if not line:
                continue
            line_norm = _normalize(line)
            if any(kw in line_norm for kw in stop_keywords):
                in_criterio_section = False
                continue
            if 'criterio' in line_norm or 'indicador' in line_norm or 'variable' in line_norm:
                in_criterio_section = True
                continue
            if _is_boilerplate(line):
                continue
            criterio = re.sub(r'^\s*(?:\d+[\.)]|•|-|✓|☐)\s*', '', line).strip()
            criterio_norm = _normalize(criterio)
            if len(criterio_norm) < 20:
                continue
            if not in_criterio_section and not re.match(r'^\s*(?:\d+[\.)]|•|-|✓|☐)\s+', line):
                continue
            if _is_boilerplate(criterio):
                continue
            rows.append({'criterio': criterio})
        return pd.DataFrame(rows)

    def _detect_dataframe_from_text(archivo_pdf):
        text = _extract_text(archivo_pdf)
        if not text:
            return None, 'texto no extraído', ''
        df = _parse_text_candidates(text)
        return df, 'texto extraído', 'criterio'

    def _detect_dataframe(archivo_pdf):
        df_tables, source, columns = _detect_dataframe_from_tables(archivo_pdf)
        if df_tables is not None and not df_tables.empty:
            return df_tables, source, columns
        df_text, text_source, text_columns = _detect_dataframe_from_text(archivo_pdf)
        if df_text is not None and not df_text.empty:
            return df_text, text_source, text_columns
        return None, source or text_source, columns or text_columns

    def _pick_col(df, *names):
        for name in names:
            norm_name = _normalize(name)
            for col in df.columns:
                if norm_name and norm_name in _normalize(col):
                    return col
        return None

    def _detect_col_by_content(df):
        best_col = None
        best_count = -1
        for col in df.columns:
            count = 0
            for value in df[col]:
                text = _clean_text(value)
                text_norm = _normalize(text)
                if _is_empty(text) or _is_boilerplate(text):
                    continue
                if len(text_norm) >= 20:
                    count += 1
            if count > best_count:
                best_count = count
                best_col = col
        return best_col if best_count >= 2 else None

    def _parse_puntaje(value):
        if _is_empty(value):
            return 10
        try:
            puntaje = int(float(str(value).replace(',', '.').strip()))
            return max(1, min(puntaje, 100))
        except (TypeError, ValueError):
            return 10

    try:
        archivo.seek(0)
        df, fuente, columnas_detectadas = _detect_dataframe(archivo)

        if df is None or df.empty:
            messages.error(
                request,
                'No se pudo leer una tabla o lista de criterios desde el PDF. '
                'El archivo debe tener texto seleccionable o una tabla con encabezado "Criterio", "Indicador" o "Variable".'
            )
            return redirect('importar_pdf_checklists')

        col_criterio = _pick_col(df, 'criterio', 'criterios', 'indicador', 'indicadores', 'variable', 'variables', 'item', 'items')
        if not col_criterio:
            col_criterio = _detect_col_by_content(df)

        if not col_criterio:
            cols_str = ' | '.join(str(c) for c in df.columns)
            messages.error(
                request,
                f'No se detectó una columna de criterios. Columnas detectadas: [{cols_str}]. '
                f'Fuente usada: {fuente}. Revise el formato esperado en esta página.'
            )
            return redirect('importar_pdf_checklists')

        col_etapa = _pick_col(df, 'etapa', 'fase')
        col_comentarios = _pick_col(
            df, 'comentario', 'comentarios', 'descripcion', 'descripción',
            'observacion', 'observaciones', 'desc'
        )
        col_puntaje = _pick_col(df, 'puntaje_maximo', 'puntaje', 'puntos', 'calificacion')

        titulo = request.POST.get('titulo', '').strip() or 'Checklist importado'
        descripcion = request.POST.get('descripcion', '').strip() or 'Importado desde PDF'

        with transaction.atomic():
            checklist = Checklist.objects.create(titulo=titulo, descripcion=descripcion, activo=True, propietario=request.user)
            seen = set()
            created_items = 0
            errores = []

            for idx, row in df.iterrows():
                fila_num = idx + 2
                try:
                    raw_criterio = row.get(col_criterio, '')
                    criterio = _clean_text(raw_criterio)
                    if _is_empty(criterio) or _is_boilerplate(criterio):
                        continue

                    criterio_norm = _normalize(criterio)
                    if criterio_norm in seen:
                        continue

                    etapa = _clean_text(row.get(col_etapa, '')) if col_etapa else ''
                    comentarios = _clean_text(row.get(col_comentarios, '')) if col_comentarios else ''
                    puntaje_maximo = _parse_puntaje(row.get(col_puntaje, 10)) if col_puntaje else 10

                    ChecklistItem.objects.create(
                        checklist=checklist,
                        competencia=None,
                        criterio=criterio[:200],
                        descripcion=comentarios,
                        puntaje_maximo=puntaje_maximo,
                        orden=created_items,
                        etapa=etapa[:50],
                    )
                    seen.add(criterio_norm)
                    created_items += 1
                except Exception as e:
                    errores.append(f'Fila {fila_num}: {str(e)}')

            if created_items == 0:
                checklist.delete()
                messages.error(
                    request,
                    'No se crearon items. El PDF debe incluir una tabla con una columna llamada '
                    '"Criterio", "Indicador" o "Variable" y filas con criterios válidos.'
                )
                return redirect('importar_pdf_checklists')

            if errores:
                messages.warning(request, 'Importación finalizó con advertencias:\n' + '\n'.join(errores[:10]))

            messages.success(
                request,
                f'Se crearon {created_items} items en el checklist "{checklist.titulo}". '
                f'Fuente detectada: {fuente}.'
            )


    except Exception as e:
        logger.error('Error en importacion PDF de checklist: %s', str(e), exc_info=True)
        messages.error(request, f'Error al procesar el archivo: {str(e)}')

    return redirect('lista_checklists')


@login_required
def importar_pdf_checklists_form(request):
    return render(request, 'evaluacion/importar_pdf_checklists.html')

