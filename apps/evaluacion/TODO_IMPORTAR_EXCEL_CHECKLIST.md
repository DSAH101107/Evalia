Pendiente: implementar importar_excel_checklists (Excel) en apps/evaluacion/views.py.

Contexto:

- apps/evaluacion/urls.py define: path('checklists/importar-excel/', views.importar_excel_checklists...)
- apps/evaluacion/views.py actualmente no contiene esa vista.
- Existe importar_pdf_checklists implementada en apps/evaluacion/views_pdf.py.

Modelos disponibles (apps/evaluacion/models.py):

- Checklist(titulo, descripcion, activo)
- ChecklistItem(competencia FK opcional, checklist FK, criterio, descripcion, puntaje_maximo, orden, etapa)

Implementación recomendada:

1. Vista importar_excel_checklists protegida con login_required.
2. Restringir acceso a rol administrador/instructor.
3. Procesar un archivo subido 'archivo_excel' (ext: .xlsx/.xls).
4. Leer con pandas (openpyxl).
5. Detectar/validar columnas mínimas del Excel. Para robustez usar mapeo por normalización.
   - sugeridas para ChecklistItem:
     - criterio: 'criterios'/'criterio'
     - descripcion: 'comentarios'/'descripcion'
     - etapa: 'etapa'
     - puntaje o casilla: 'puntaje' o 'casilla si'/'si'/'casilla'
     - checklist/titulo/descripcion: columnas 'titulo'/'checklist' o crear 1 checklist por hoja/página
6. Crear checklist(s) y luego items con orden incremental.
7. Mensajes de error por archivo/columnas y redirect a lista_checklists.

Primer paso para terminar: definir el formato exacto del Excel esperado (nombres de columnas).
