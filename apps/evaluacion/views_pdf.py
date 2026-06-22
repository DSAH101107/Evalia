from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Aprendiz, Checklist, ChecklistItem, Fase, GAES, Ficha
from apps.usuarios.models import Usuario, Rol

import logging

logger = logging.getLogger(__name__)

import pdfplumber
import pandas as pd
from io import BytesIO
import re


@login_required
def importar_pdf_aprendices(request):
    if request.method == 'GET':
        gaes_list = GAES.objects.order_by('nombre')
        return render(request, 'evaluacion/importar_pdf_aprendices.html', {
            'gaes_list': gaes_list,
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
        col_gaes = pick_col('gaes')
        col_ficha = pick_col('ficha')
        col_trimestre = pick_col('trimestre')

        logger.debug("Columnas detectadas -> nombre: %s, apellido: %s, programa: %s, gaes: %s, ficha: %s, trimestre: %s",
                     col_nombre, col_apellido, col_programa, col_gaes, col_ficha, col_trimestre)

        default_gaes = request.POST.get('default_gaes', '').strip()
        default_fase_id = request.POST.get('default_fase', '').strip()
        logger.debug("Default GAES: '%s', Default Fase ID: '%s'", default_gaes, default_fase_id)

        for i, (_, row) in enumerate(df.iterrows()):
            nombre = str(row.get(col_nombre, '')).strip() if col_nombre else ''
            apellido = str(row.get(col_apellido, '')).strip() if col_apellido else ''
            programa = str(row.get(col_programa, '')).strip() if col_programa else ''
            gaes_val = str(row.get(col_gaes, '')).strip() if col_gaes else ''
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

            gaes_obj = None
            if gaes_val:
                gaes_obj, _ = GAES.objects.get_or_create(nombre=gaes_val, defaults={'descripcion': ''})
                logger.debug("Fila %d -> GAES encontrado/creado: '%s' (id=%s)", i, gaes_val, gaes_obj.id)
            elif default_gaes:
                gaes_obj, _ = GAES.objects.get_or_create(nombre=default_gaes, defaults={'descripcion': ''})
                logger.debug("Fila %d -> GAES default usado: '%s' (id=%s)", i, default_gaes, gaes_obj.id)

            ficha_obj = None
            if ficha_val:
                if gaes_obj:
                    ficha_obj, _ = Ficha.objects.get_or_create(numero=ficha_val, defaults={'gaes': gaes_obj})
                else:
                    ficha_obj, _ = Ficha.objects.get_or_create(numero=ficha_val)
                logger.debug("Fila %d -> Ficha encontrada/creada: '%s' (id=%s, gaes_id=%s)",
                             i, ficha_val, ficha_obj.id, ficha_obj.gaes_id)

            fase_obj = None
            if default_fase_id:
                fase_obj = Fase.objects.filter(numero=default_fase_id).first()
                if fase_obj:
                    logger.debug("Fila %d -> Fase default usada: %s (id=%s)", i, default_fase_id, fase_obj.id)
                else:
                    logger.warning("Fila %d -> Fase default '%s' no encontrada en BD", i, default_fase_id)

            # Asignar propietario solo si el usuario es instructor
            propietario = request.user if request.user.rol == 'instructor' else None

            aprendiz, created_new = Aprendiz.objects.update_or_create(
                documento=documento,
                defaults={
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
            )
            logger.info("Fila %d -> Aprendiz %s (documento='%s', id=%d, fase_id=%s)",
                        i, 'CREADO' if created_new else 'ACTUALIZADO', documento, aprendiz.id,
                        aprendiz.fase_id)

            # Actualizar propietario si es instructor y no lo tiene asignado
            if propietario and not aprendiz.propietario:
                aprendiz.propietario = propietario
                aprendiz.save()
                logger.debug("Fila %d -> Propietario asignado: usuario_id=%s", i, propietario.id)

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
    created_items = 0
    errores = []

    def _norm_col(s):
        s = '' if s is None else str(s)
        s = s.strip().lower()
        s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        s = s.replace('ñ', 'n')
        return s

    try:
        with pdfplumber.open(BytesIO(archivo.read())) as pdf:
            best_table = None
            best_score = -1

            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                for table in tables:
                    if not table or len(table) < 2 or not table[0]:
                        continue
                    headers = [_norm_col(h) for h in table[0] if h]
                    score = sum(1 for h in headers if 'criterio' in h or 'indicador' in h or 'variable' in h)
                    if score > best_score and score > 0:
                        best_score = score
                        best_table = table

            if not best_table:
                messages.error(request, 'No se encontró tabla con columnas de criterios')
                return redirect('lista_checklists')

            df = pd.DataFrame(best_table[1:], columns=[_norm_col(c) for c in best_table[0]])

            col_criterio = next((h for h in df.columns if 'criterio' in h or 'indicador' in h or 'variable' in h), None)
            col_etapa = next((h for h in df.columns if 'etapa' in h), None)
            col_comentarios = next((h for h in df.columns if 'comentario' in h or 'descripcion' in h), None)

            titulo = request.POST.get('titulo', '').strip() or 'Checklist importado'
            descripcion = request.POST.get('descripcion', '').strip() or f'Importado desde PDF'

            checklist = Checklist.objects.create(titulo=titulo, descripcion=descripcion, activo=True)

            for idx, row in df.iterrows():
                criterio_raw = row.get(col_criterio, '') if col_criterio else ''
                criterio_str = str(criterio_raw).strip() if criterio_raw is not None else ''
                if not criterio_str or criterio_str.lower() in ['nan', 'none', 'null', '', '*']:
                    continue

                etapa = str(row.get(col_etapa, '')).strip() if col_etapa else ''
                comentarios = str(row.get(col_comentarios, '')).strip() if col_comentarios else ''

                ChecklistItem.objects.create(
                    checklist=checklist,
                    criterio=criterio_str,
                    descripcion=comentarios,
                    puntaje_maximo=10,
                    etapa=etapa,
                    orden=len(checklist.items.all()),
                )
                created_items += 1

            messages.success(request, f'Se crearon {created_items} items en el checklist "{checklist.titulo}"')

    except Exception as e:
        messages.error(request, f'Error: {str(e)}')

    return redirect('lista_checklists')


@login_required
def importar_pdf_checklists_form(request):
    return render(request, 'evaluacion/importar_pdf_checklists.html')

