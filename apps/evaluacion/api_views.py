# apps/evaluacion/api_views.py
"""
DRF ViewSets / APIViews para EVALIA.
Endpoints REST disponibles bajo /api/.
Permisos por rol controlados por cada ViewSet.
"""

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
import logging

logger = logging.getLogger(__name__)

from . import serializers as slz
from .models import (
    Aprendiz, Evaluacion, EvaluacionItem,
    Resultado, Invitacion, Checklist, ChecklistItem,
    Fase, Competencia, GAES, Ficha,
)
from apps.usuarios.models import Usuario, Rol

# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _is_admin(user):      return user.rol == Rol.ADMINISTRADOR
def _is_instructor(user): return user.rol == Rol.INSTRUCTOR
def _is_jurado(user):     return user.rol == Rol.JURADO
def _is_aprendiz(user):   return user.rol == Rol.APRENDIZ


# ──────────────────────────────────────────────────────────
# Paginador estándar
# ──────────────────────────────────────────────────────────

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# ──────────────────────────────────────────────────────────
# ViewSet: Aprendiz
# ──────────────────────────────────────────────────────────

class AprendizViewSet(viewsets.ModelViewSet):
    queryset = Aprendiz.objects.select_related('ficha', 'gaes', 'fase').all()
    serializer_class = slz.AprendizSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['documento', 'nombres', 'apellidos', 'email',
                     'programa', 'ficha__numero', 'gaes__nombre']
    ordering_fields = ['nombres', 'apellidos', 'documento', 'created_at']
    ordering = ['nombres']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_admin(self.request.user):
            return qs
        if _is_instructor(self.request.user):
            return qs.filter(propietario=self.request.user)
        if _is_jurado(self.request.user):
            return qs.filter(ficha__evaluaciones__juror=self.request.user).distinct()
        return Aprendiz.objects.none()

    @action(detail=True, methods=['post'])
    def bloquear(self, request, pk=None):
        aprendiz = self.get_object()
        aprendiz.bloqueado = not aprendiz.bloqueado
        aprendiz.save(update_fields=['bloqueado'])
        return Response({'success': True, 'bloqueado': aprendiz.bloqueado})

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """Resumen de aprendices por GAES/Ficha/Fase."""
        gaes_qs = (GAES.objects
                   .annotate(cant=Count('aprendices', distinct=True))
                   .filter(cant__gt=0).order_by('nombre'))
        ficha_qs = (Ficha.objects
                    .annotate(cant=Count('aprendices', distinct=True))
                    .filter(cant__gt=0).order_by('numero'))
        fase_qs  = (Fase.objects
                    .annotate(cant=Count('aprendices', distinct=True))
                    .order_by('numero'))
        return Response({
            'gaes_labels':  [g.nombre for g in gaes_qs],
            'gaes_values':  [g.cant  for g in gaes_qs],
            'ficha_labels': [f.numero for f in ficha_qs],
            'ficha_values': [f.cant  for f in ficha_qs],
            'fase_labels':  [f'Fase {f.numero}' for f in fase_qs],
            'fase_values':  [f.cant  for f in fase_qs],
        })


# ──────────────────────────────────────────────────────────
# ViewSet: Evaluacion
# ──────────────────────────────────────────────────────────

class EvaluacionViewSet(viewsets.ModelViewSet):
    queryset = (Evaluacion.objects
                .select_related('aprendiz', 'juror', 'checklist')
                .order_by('-fecha'))
    serializer_class = slz.EvaluacionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'aprendiz__nombres', 'aprendiz__apellidos',
        'juror__username', 'checklist__titulo',
    ]
    ordering_fields = ['fecha', 'calificacion_total', 'estado']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_admin(self.request.user):
            return qs
        if _is_instructor(self.request.user) or _is_jurado(self.request.user):
            return qs.filter(juror=self.request.user)
        return Evaluacion.objects.none()

    @action(detail=True, methods=['get', 'post'])
    def items(self, request, pk=None):
        """Get/set EvaluationItems for a specific Evaluacion."""
        evaluacion = self.get_object()
        if request.method == 'GET':
            items = (EvaluacionItem.objects
                     .filter(evaluacion=evaluacion)
                     .select_related('item__competencia'))
            return Response(
                slz.EvaluacionItemSerializer(items, many=True).data
            )

        # POST → create/update
        items_data = request.data.get('items', [])
        creados = 0
        for item_data in items_data:
            evaluacion_item, _ = EvaluacionItem.objects.get_or_create(
                evaluacion=evaluacion,
                item_id=item_data['item'],
            )
            evaluacion_item.puntaje      = item_data.get('puntaje', 0)
            evaluacion_item.observaciones = item_data.get('observaciones', '')
            evaluacion_item.save()
            creados += 1
        return Response({'created': creados, 'evaluacion_id': pk})

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        """Marca evaluación como completada y calcula calificación total."""
        evaluacion = self.get_object()
        evaluacion.estado = Evaluacion.ESTADO_COMPLETADA
        evaluacion.calcular_puntaje()
        evaluacion.save()
        # Crear/actualizar resultado
        from .models import Resultado
        resultado, _ = Resultado.objects.get_or_create(
            aprendiz=evaluacion.aprendiz
        )
        resultado.calcular_resultado()
        return Response({'success': True, 'estado': 'completada'})


# ──────────────────────────────────────────────────────────
# ViewSet: Resultado
# ──────────────────────────────────────────────────────────

class ResultadoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (Resultado.objects
                .select_related('aprendiz__ficha', 'aprendiz__gaes', 'aprendiz__fase')
                .order_by('-fecha_cierre'))
    serializer_class = slz.ResultadoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['aprendiz__nombres', 'aprendiz__apellidos', 'aprendiz__documento']
    ordering_fields = ['fecha_cierre', 'promedio', 'calificacion_final']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_admin(self.request.user):
            return qs
        if _is_instructor(self.request.user) or _is_jurado(self.request.user):
            return qs.filter(aprendiz__evaluaciones__juror=self.request.user).distinct()
        if _is_aprendiz(self.request.user):
            try:
                aprendiz = Aprendiz.objects.get(usuario=self.request.user)
                return qs.filter(aprendiz=aprendiz)
            except Aprendiz.DoesNotExist:
                return Resultado.objects.none()
        return Resultado.objects.none()


# ──────────────────────────────────────────────────────────
# ViewSet: Invitacion
# ──────────────────────────────────────────────────────────

class InvitacionViewSet(viewsets.ModelViewSet):
    queryset = Invitacion.objects.select_related(
        'instructor', 'instructor_invitado', 'ficha'
    ).prefetch_related('instructores_jurados').order_by('-fecha_envio')
    serializer_class = slz.InvitacionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'instructor__username', 'instructor_invitado__username',
        'estado', 'ficha__numero',
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_admin(self.request.user):
            return qs
        if _is_instructor(self.request.user):
            return qs.filter(instructor=self.request.user)
        if _is_jurado(self.request.user):
            return qs.filter(instructores_jurados=self.request.user)
        return Invitacion.objects.none()

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)

    @action(detail=True, methods=['post'])
    def aceptar(self, request, pk=None):
        invitacion = self.get_object()
        invitacion.estado = Invitacion.ESTADO_ACEPTADA
        invitacion.instructor_invitado = request.user
        from django.utils import timezone
        invitacion.fecha_respuesta = timezone.now()
        invitacion.save()
        if request.user.rol != 'jurado':
            request.user.rol = 'jurado'
            request.user.save(update_fields=['rol'])
        return Response({'success': True, 'message': 'Invitación aceptada'})

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        invitacion = self.get_object()
        invitacion.estado = Invitacion.ESTADO_RECHAZADA
        from django.utils import timezone
        invitacion.fecha_respuesta = timezone.now()
        invitacion.save()
        return Response({'success': True, 'message': 'Invitación rechazada'})


# ──────────────────────────────────────────────────────────
# ViewSet: Estadísticas
# ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_estadisticas(request):
    """Estadísticas generales del sistema."""
    total_aprendices = Aprendiz.objects.count()
    total_evaluaciones = Evaluacion.objects.count()
    total_resultados = Resultado.objects.count()
    pendientes      = Evaluacion.objects.filter(estado=Evaluacion.ESTADO_PENDIENTE).count()
    completadas     = Evaluacion.objects.filter(estado=Evaluacion.ESTADO_COMPLETADA).count()
    return Response({
        'aprendices':  total_aprendices,
        'evaluaciones': total_evaluaciones,
        'resultados':  total_resultados,
        'pendientes':  pendientes,
        'completadas': completadas,
    })
