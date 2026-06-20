from django.contrib import admin
from .models import (
    Aprendiz,
    Evaluacion, EvaluacionItem,
    Resultado, Invitacion,
    GAES,
    Fase,
    Ficha,
    Competencia,
    Checklist,
    ChecklistItem,
    Trimestre,
    ResultadoAprendizaje,
)


# ── GAES ──────────────────────────────────────────────

@admin.register(GAES)
class GAESAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'descripcion', 'activo', 'cant_fichas', 'cant_aprendices')
    search_fields = ('nombre', 'descripcion')
    list_filter   = ('activo',)
    ordering = ['nombre']

    def cant_fichas(self, obj):
        return obj.fichas.count()
    cant_fichas.short_description = 'Fichas'

    def cant_aprendices(self, obj):
        return obj.aprendices.count()
    cant_aprendices.short_description = 'Aprendices'


# ── FASE ──────────────────────────────────────────────

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display  = ('numero', 'nombre', 'cant_competencias', 'cant_aprendices')
    search_fields = ('nombre',)
    ordering = ['numero']

    def cant_competencias(self, obj):
        return obj.competencias.count()
    cant_competencias.short_description = 'Competencias'

    def cant_aprendices(self, obj):
        return obj.aprendices.count()
    cant_aprendices.short_description = 'Aprendices'


# ── TRIMESTRE ─────────────────────────────────────────

@admin.register(Trimestre)
class TrimestreAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'nombre', 'anio', 'fecha_inicio', 'fecha_fin', 'activo',
                     'cant_fichas', 'cant_competencias')
    search_fields = ('nombre', 'numero', 'anio')
    list_filter   = ('activo', 'anio')
    ordering = ['-anio', 'numero']

    def cant_fichas(self, obj):
        return obj.fichas.count()
    cant_fichas.short_description = 'Fichas'

    def cant_competencias(self, obj):
        return obj.competencias.count()
    cant_competencias.short_description = 'Competencias'


# ── FICHA ─────────────────────────────────────────────

@admin.register(Ficha)
class FichaAdmin(admin.ModelAdmin):
    list_display  = ('numero', 'programa', 'jornada', 'gaes', 'trimestre',
                     'instructor', 'estado', 'cant_aprendices')
    search_fields = ('numero', 'programa')
    list_filter   = ('jornada', 'estado', 'gaes', 'trimestre', 'instructor')
    ordering = ['numero']

    def cant_aprendices(self, obj):
        return obj.aprendices.count()
    cant_aprendices.short_description = 'Aprendices'


# ── RESULTADO DE APRENDIZAJE ──────────────────────────

@admin.register(ResultadoAprendizaje)
class ResultadoAprendizajeAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre', 'trimestre')
    search_fields = ('codigo', 'nombre')
    list_filter   = ('trimestre',)
    ordering = ['codigo']


# ── COMPETENCIA ──────────────────────────────────────

@admin.register(Competencia)
class CompetenciaAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre', 'fase', 'gaes', 'ficha', 'trimestre', 'activo')
    search_fields = ('codigo', 'nombre', 'descripcion')
    list_filter   = ('fase', 'gaes', 'ficha', 'trimestre', 'activo')
    ordering = ['codigo']


# ── CHECKLIST ────────────────────────────────────────

@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display  = ('titulo', 'descripcion', 'activo', 'cant_items', 'fecha_creacion')
    search_fields = ('titulo', 'descripcion')
    list_filter   = ('activo',)
    ordering = ['-id']

    def cant_items(self, obj):
        return obj.items.count()
    cant_items.short_description = 'Items'

    def fecha_creacion(self, obj):
        from django.utils import timezone
        return timezone.now().strftime('%Y-%m-%d') if obj.id else '—'
    fecha_creacion.short_description = 'Creado'


# ── CHECKLIST ITEM ───────────────────────────────────

@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'competencia', 'puntaje_maximo', 'orden', 'etapa')
    search_fields = ('criterio', 'descripcion', 'competencia__codigo', 'competencia__nombre')
    list_filter   = ('competencia', 'etapa')
    ordering = ['competencia__codigo', 'orden']


# ── APRENDIZ ─────────────────────────────────────────

@admin.register(Aprendiz)
class AprendizAdmin(admin.ModelAdmin):
    list_display = ('documento', 'nombres', 'apellidos', 'email', 'ficha', 'gaes', 'fase', 'bloqueado')
    search_fields = ('documento', 'nombres', 'apellidos', 'email', 'programa')
    list_filter  = ('bloqueado', 'ficha', 'gaes', 'fase')
    ordering = ['nombres']


# ── EVALUACION ───────────────────────────────────────

@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ('aprendiz', 'juror', 'checklist', 'estado', 'fecha')
    search_fields = ('aprendiz__nombres', 'aprendiz__apellidos', 'juror__username')
    list_filter  = ('estado', 'fecha')
    ordering = ['-fecha']


# ── EVALUACION ITEM ──────────────────────────────────

@admin.register(EvaluacionItem)
class EvaluacionItemAdmin(admin.ModelAdmin):
    list_display = ('evaluacion', 'item', 'puntaje', 'observaciones_c')
    search_fields = ('evaluacion__aprendiz__nombres', 'item__criterio')
    ordering = ['-evaluacion__fecha']

    def observaciones_c(self, obj):
        return (obj.observaciones or '')[:50]
    observaciones_c.short_description = 'Observaciones'


# ── RESULTADO ────────────────────────────────────────

@admin.register(Resultado)
class ResultadoAdmin(admin.ModelAdmin):
    list_display = ('aprendiz', 'promedio', 'calificacion_final', 'fecha_cierre')
    search_fields = ('aprendiz__nombres', 'aprendiz__apellidos')
    ordering = ['-fecha_cierre']


# ── INVITACION ───────────────────────────────────────

@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'instructor_invitado', 'estado', 'fecha_envio', 'fecha_evaluacion')
    list_filter  = ('estado',)
    search_fields = ('instructor__username', 'instructor_invitado__username')
    ordering = ['-fecha_envio']

