# apps/evaluacion/serializers/serializers_aprendiz.py
from rest_framework import serializers
from apps.evaluacion.models import Aprendiz


class AprendizSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='__str__', read_only=True)
    gaes_nombre     = serializers.CharField(source='gaes.nombre',   read_only=True)
    fase_numero     = serializers.CharField(source='fase.numero',   read_only=True)
    ficha_numero    = serializers.CharField(source='ficha.numero',  read_only=True)

    class Meta:
        model = Aprendiz
        fields = [
            'id', 'documento', 'nombres', 'apellidos', 'email', 'telefono',
            'nombre_completo', 'ficha', 'ficha_numero', 'gaes', 'gaes_nombre',
            'fase', 'fase_numero', 'programa', 'trimestre',
            'bloqueado', 'fecha_nacimiento', 'direccion',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
