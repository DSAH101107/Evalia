# apps/evaluacion/serializers/serializers_evaluacion.py
from rest_framework import serializers
from apps.evaluacion.models import Evaluacion, EvaluacionItem


class EvaluacionSerializer(serializers.ModelSerializer):
    aprendiz_nombre = serializers.CharField(source='aprendiz.__str__', read_only=True)
    jurado_username = serializers.CharField(source='juror.username', read_only=True)
    checklist_titulo = serializers.CharField(source='checklist.titulo', read_only=True)

    class Meta:
        model = Evaluacion
        fields = [
            'id', 'aprendiz', 'aprendiz_nombre', 'juror', 'jurado_username',
            'checklist', 'checklist_titulo', 'fecha',
            'observaciones', 'calificacion_total', 'estado',
        ]
        read_only_fields = ['id', 'fecha', 'calificacion_total']


class EvaluacionItemSerializer(serializers.ModelSerializer):
    item_criterio = serializers.CharField(source='item.criterio', read_only=True)
    item_punt_max = serializers.IntegerField(source='item.puntaje_maximo', read_only=True)

    class Meta:
        model = EvaluacionItem
        fields = [
            'id', 'evaluacion', 'item', 'item_criterio', 'item_punt_max',
            'puntaje', 'observaciones',
        ]
        read_only_fields = ['id']
