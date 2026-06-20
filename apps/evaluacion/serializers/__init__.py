"""
apps/evaluacion/serializers/__init__.py
DRF Serializers para todos los modelos del dominio de evaluación.
"""
from .serializers_aprendiz import AprendizSerializer
from .serializers_evaluacion import EvaluacionSerializer, EvaluacionItemSerializer
from .serializers_resultados import ResultadoSerializer, InvitacionSerializer, ChecklistSerializer, ChecklistItemSerializer

__all__ = [
    'AprendizSerializer', 'EvaluacionSerializer', 'EvaluacionItemSerializer',
    'ResultadoSerializer', 'InvitacionSerializer', 'ChecklistSerializer', 'ChecklistItemSerializer',
]
