# apps/gaes/serializers.py
from rest_framework import serializers
from apps.evaluacion.models import GAES, Aprendiz


class GAESSerializer(serializers.ModelSerializer):
    cantidad_aprendices = serializers.IntegerField(read_only=True)
    cantidad_fichas = serializers.IntegerField(read_only=True)
    ficha_numero = serializers.CharField(source='ficha.numero', read_only=True)

    class Meta:
        model = GAES
        fields = ['id', 'nombre', 'descripcion', 'activo', 'ficha', 'ficha_numero',
                  'cantidad_aprendices', 'cantidad_fichas']


class AprendizGAESSerializer(serializers.ModelSerializer):
    ficha_numero = serializers.CharField(source='ficha.numero', read_only=True)

    class Meta:
        model = Aprendiz
        fields = ['id', 'nombres', 'apellidos', 'documento', 'ficha_numero', 'gaes']
