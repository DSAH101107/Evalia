# apps/fichas/serializers.py
from rest_framework import serializers
from .models import Ficha


class FichaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ficha
        fields = [
            'id', 'numero', 'programa', 'jornada',
            'gaes', 'trimestre', 'instructor', 'estado',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
