"""
apps/evaluacion/models.py

Domain models consolidated here to maintain a single source of truth.
Split apps (gaes, fichas, trimestres, competencias) re-export from here.

NOTE: Cross-app FK imports (GAES, Ficha, Fase, Competencia, ChecklistItem)
are lazy-loaded inside functions to avoid circular imports during app
registry population.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.usuarios.models import Usuario


# ──────────────────────────────────────────────────────────
# Lazy cross-app registries (resolved on first access)
# ──────────────────────────────────────────────────────────

_GAES    = None
_Ficha   = None
_Fase    = None
_Competencia = None
_Checklist   = None
_ChecklistItem = None


def _get_gaes():
    global _GAES
    if _GAES is None:
        from apps.evaluacion.models import GAES as _g
        _GAES = _g
    return _GAES


def _get_ficha():
    global _Ficha
    if _Ficha is None:
        from apps.fichas.models import Ficha
        _Ficha = Ficha
    return _Ficha


def _get_fase():
    global _Fase
    if _Fase is None:
        from apps.competencias.models import Fase
        _Fase = Fase
    return _Fase


def _get_competencia():
    global _Competencia
    if _Competencia is None:
        from apps.competencias.models import Competencia
        _Competencia = Competencia
    return _Competencia


def _get_checklist():
    global _Checklist
    if _Checklist is None:
        from apps.competencias.models import Checklist
        _Checklist = Checklist
    return _Checklist


def _get_checklistitem():
    global _ChecklistItem
    if _ChecklistItem is None:
        from apps.competencias.models import ChecklistItem
        _ChecklistItem = ChecklistItem
    return _ChecklistItem


# ============================================
# GAES (Grupo de Aprendices de Evaluación y Sustentación)
# ============================================

class GAES(models.Model):
    nombre        = models.CharField(max_length=120)
    descripcion   = models.TextField(blank=True, default='')
    ficha = models.ForeignKey(
        'Ficha', on_delete=models.SET_NULL, related_name='grupos', null=True, blank=True)
    activo        = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = "GAES"
        verbose_name_plural = "GAES"

    def __str__(self):
        return self.nombre


# ============================================
# FASE
# ============================================

class Fase(models.Model):
    numero = models.PositiveSmallIntegerField(unique=True)
    nombre = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        ordering = ['numero']

    def clean(self):
        if not (1 <= int(self.numero) <= 7):
            raise ValidationError({'numero': 'La fase debe estar entre 1 y 7.'})

    def __str__(self):
        return f"Fase {self.numero}"


# ============================================
# FICHA
# ============================================

class Ficha(models.Model):
    numero      = models.CharField(max_length=30, unique=True)
    programa    = models.CharField(max_length=200, blank=True, default='')
    jornada     = models.CharField(
        max_length=50,
        choices=[('mañana','Mañana'),('tarde','Tarde'),('noche','Noche'),('mixto','Mixto')],
        blank=True, default='mañana',
    )
    gaes        = models.ForeignKey(GAES, on_delete=models.PROTECT, related_name='fichas', null=True, blank=True)
    trimestre   = models.ForeignKey(
        'Trimestre', on_delete=models.SET_NULL, null=True, blank=True, related_name='fichas'
    )
    instructor  = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fichas_asignadas',
    )
    estado = models.CharField(
        max_length=20,
        choices=[('activo','Activo'),('finalizado','Finalizado'),('suspendido','Suspendido')],
        default='activo',
    )

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return self.numero


# ============================================
# TRIMESTRE
# ============================================

class Trimestre(models.Model):
    numero      = models.PositiveSmallIntegerField()
    nombre      = models.CharField(max_length=120, blank=True, default='')
    anio        = models.PositiveIntegerField(null=True, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin   = models.DateField(null=True, blank=True)
    activo      = models.BooleanField(default=True)

    class Meta:
        ordering = ['-anio', 'numero']
        unique_together = ('numero', 'anio')

    def __str__(self):
        return f"Trimestre {self.numero} ({self.anio or ''})"


class ResultadoAprendizaje(models.Model):
    codigo    = models.CharField(max_length=60, unique=True)
    nombre    = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default='')
    trimestre = models.ForeignKey(Trimestre, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='resultados_aprendizaje')

    class Meta:
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


# ============================================
# COMPETENCIA
# ============================================

class Competencia(models.Model):
    codigo       = models.CharField(max_length=60, unique=True)
    nombre       = models.CharField(max_length=200)
    descripcion  = models.TextField(blank=True, default='')
    fase         = models.ForeignKey(Fase,      on_delete=models.PROTECT, related_name='competencias')
    gaes         = models.ForeignKey(GAES,      on_delete=models.PROTECT, related_name='competencias', null=True, blank=True)
    ficha = models.ForeignKey(Ficha,     on_delete=models.SET_NULL, related_name='competencias', null=True, blank=True)
    trimestre    = models.ForeignKey(Trimestre, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='competencias')
    activo       = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


# ============================================
# CHECKLIST & ITEMS
# ============================================

class Checklist(models.Model):
    titulo     = models.CharField(max_length=100)
    descripcion = models.TextField()
    activo     = models.BooleanField(default=True)
    propietario = models.ForeignKey('usuarios.Usuario', null=True, blank=True, on_delete=models.SET_NULL, related_name='checklists')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.titulo


class ChecklistItem(models.Model):
    competencia  = models.ForeignKey(Competencia, on_delete=models.PROTECT,
                                     null=True, blank=True, related_name='items')
    checklist    = models.ForeignKey(Checklist, on_delete=models.CASCADE,
                                     related_name='items', null=True, blank=True)
    criterio     = models.CharField(max_length=200)
    descripcion  = models.TextField()
    puntaje_maximo = models.IntegerField(default=10)
    orden        = models.IntegerField(default=0)
    etapa        = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['competencia__codigo', 'orden']

    def __str__(self):
        comp = getattr(self.competencia, 'codigo', '—')
        return f"{comp} | {self.criterio}"


# ============================================
# APRENDIZ
# ============================================

class Aprendiz(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE,
                                   related_name='aprendiz', null=True, blank=True)
    propietario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, related_name='aprendices_propietario',
        null=True, blank=True,
    )
    documento      = models.CharField(max_length=20, unique=True)
    nombres        = models.CharField(max_length=100)
    apellidos      = models.CharField(max_length=100)
    email          = models.EmailField()
    telefono       = models.CharField(max_length=20, blank=True)
    ficha          = models.ForeignKey(Ficha,   on_delete=models.SET_NULL,  related_name='aprendices', null=True, blank=True)
    gaes           = models.ForeignKey(GAES,    on_delete=models.PROTECT,  related_name='aprendices', null=True, blank=True)
    fase           = models.ForeignKey(Fase,    on_delete=models.PROTECT,  related_name='aprendices', null=True, blank=True)
    programa       = models.CharField(max_length=100, blank=True, default='')
    trimestre      = models.CharField(max_length=10, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion      = models.TextField(blank=True)
    bloqueado      = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombres']

    def __str__(self):
        s = f"{self.nombres} {self.apellidos} ({self.documento})"
        if self.bloqueado:
            return s + ' [Bloqueado]'
        else:
            return s + ' [Activo]'

    def get_promedio(self):
        if self.bloqueado:
            return 0
        r = Resultado.objects.filter(aprendiz=self)
        return sum(x.promedio for x in r) / r.count() if r.exists() else 0


# ============================================
# EVALUACION
# ============================================

class Evaluacion(models.Model):
    ESTADO_PENDIENTE  = 'pendiente'
    ESTADO_COMPLETADA = 'completada'
    ESTADO_CANCELADA  = 'cancelada'

    aprendiz       = models.ForeignKey(Aprendiz, on_delete=models.CASCADE, related_name='evaluaciones')
    juror          = models.ForeignKey(Usuario,  on_delete=models.CASCADE, related_name='evaluaciones_realizadas')
    checklist      = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='evaluaciones')
    fecha          = models.DateTimeField(auto_now_add=True)
    observaciones  = models.TextField(blank=True)
    calificacion_total = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    estado = models.CharField(max_length=20,
        choices=[(ESTADO_PENDIENTE,'Pendiente'),(ESTADO_COMPLETADA,'Completada'),(ESTADO_CANCELADA,'Cancelada')],
        default=ESTADO_PENDIENTE)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.aprendiz} - {self.juror} - {self.checklist.titulo}"

    def calcular_puntaje(self):
        items_q = ChecklistItem.objects.filter(
            competencia__fase=self.aprendiz.fase
        ) if self.aprendiz and self.aprendiz.fase_id else ChecklistItem.objects.none()
        total = sum(
            (EvaluacionItem.objects.filter(evaluacion=self, item=item).first() or type('X', (), {'puntaje': 0})()).puntaje
            for item in items_q
        )
        self.calificacion_total = total
        self.save()


# ============================================
# EVALUACION ITEM
# ============================================

class EvaluacionItem(models.Model):
    evaluacion   = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name='items')
    item         = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE)
    puntaje      = models.IntegerField(default=0)
    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = ('evaluacion', 'item')

    def __str__(self):
        return f"{self.evaluacion} - {self.item.criterio}: {self.puntaje}"


# ============================================
# RESULTADO
# ============================================

class Resultado(models.Model):
    aprendiz           = models.ForeignKey(Aprendiz, on_delete=models.CASCADE, related_name='resultados')
    promedio           = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    calificacion_final = models.CharField(max_length=10, default='No evaluado')
    fecha_cierre       = models.DateTimeField(auto_now_add=True)
    observaciones_generales = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_cierre']

    def __str__(self):
        return f"{self.aprendiz} - Promedio: {self.promedio}"

    def calcular_resultado(self):
        evals = Evaluacion.objects.filter(aprendiz=self.aprendiz, estado=Evaluacion.ESTADO_COMPLETADA)
        if evals.exists():
            self.promedio = sum(float(e.calificacion_total) for e in evals) / evals.count()
            self.calificacion_final = getattr(evals.latest('fecha').juror, 'username', 'No evaluado')
            self.save()


# ============================================
# INVITACION
# ============================================

class Invitacion(models.Model):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ACEPTADA  = 'aceptada'
    ESTADO_RECHAZADA = 'rechazada'

    instructor          = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='invitaciones_enviadas')
    instructor_invitado = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='invitaciones_recibidas',
                                            null=True, blank=True)
    ficha = models.ForeignKey(Ficha, on_delete=models.CASCADE, related_name='invitaciones', null=True, blank=True)
    instructores_jurados = models.ManyToManyField(Usuario, related_name='invitaciones_como_jurado', blank=True)
    checklist = models.ForeignKey('Checklist', on_delete=models.SET_NULL, related_name='invitaciones',
                                null=True, blank=True)
    estado = models.CharField(max_length=20,
        choices=[(ESTADO_PENDIENTE,'Pendiente'),(ESTADO_ACEPTADA,'Aceptada'),(ESTADO_RECHAZADA,'Rechazada')],
        default=ESTADO_PENDIENTE)
    fecha_envio      = models.DateTimeField(auto_now_add=True)
    fecha_respuesta  = models.DateTimeField(null=True, blank=True)
    fecha_evaluacion = models.DateField(null=True, blank=True)
    hora_evaluacion  = models.TimeField(null=True, blank=True)
    mensaje          = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"Invitación de {self.instructor} a {self.instructor_invitado}"
