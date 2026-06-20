# apps/trimestres/serializers.py
from rest_framework import serializers
from .models import Trimestre, ResultadoAprendizaje


class TrimestreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trimestre
        fields = ['id', 'numero', 'nombre', 'anio', 'fecha_inicio', 'fecha_fin', 'activo', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResultadoAprendizajeSerializer(serializers.ModelSerializer):
    trimestre_nombre = serializers.CharField(source='trimestre.__str__', read_only=True)

    class Meta:
        model = ResultadoAprendizaje
        fields = ['id', 'codigo', 'nombre', 'descripcion', 'trimestre', 'trimestre_nombre',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
