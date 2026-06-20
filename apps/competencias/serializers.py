# apps/competencias/serializers.py
from rest_framework import serializers
from .models import Fase, Competencia, Checklist, ChecklistItem


class FaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fase
        fields = ['id', 'numero', 'nombre']
        read_only_fields = ['id']


class CompetenciaSerializer(serializers.ModelSerializer):
    fase_nombre   = serializers.CharField(source='fase.__str__', read_only=True)
    gaes_nombre   = serializers.CharField(source='gaes.nombre', read_only=True)
    ficha_numero  = serializers.CharField(source='ficha.numero', read_only=True)
    trimestre_str = serializers.CharField(source='trimestre.__str__', read_only=True)

    class Meta:
        model = Competencia
        fields = [
            'id', 'codigo', 'nombre', 'descripcion',
            'fase', 'fase_nombre', 'gaes', 'gaes_nombre',
            'ficha', 'ficha_numero', 'trimestre', 'trimestre_str',
            'activo', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChecklistItemSerializer(serializers.ModelSerializer):
    competencia_codigo = serializers.CharField(source='competencia.codigo', read_only=True)
    competencia_nombre = serializers.CharField(source='competencia.nombre', read_only=True)

    class Meta:
        model = ChecklistItem
        fields = [
            'id', 'checklist', 'competencia', 'competencia_codigo', 'competencia_nombre',
            'criterio', 'descripcion', 'puntaje_maximo', 'orden', 'etapa',
        ]
        read_only_fields = ['id']


class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)
    cantidad_items = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = Checklist
        fields = [
            'id', 'titulo', 'descripcion', 'activo',
            'cantidad_items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
