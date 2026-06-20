# apps/evaluacion/serializers/serializers_resultados.py
from rest_framework import serializers
from apps.evaluacion.models import Resultado, Invitacion, Checklist, ChecklistItem
from apps.usuarios.models import Usuario, Rol


class ResultadoSerializer(serializers.ModelSerializer):
    aprendiz_nombre = serializers.CharField(source='aprendiz.__str__', read_only=True)
    aprendiz_ficha  = serializers.CharField(source='aprendiz.ficha.__str__', read_only=True)
    calificacion_display = serializers.CharField(source='get_calificacion_final_display', read_only=True)

    class Meta:
        model = Resultado
        fields = [
            'id', 'aprendiz', 'aprendiz_nombre', 'aprendiz_ficha',
            'promedio', 'calificacion_final', 'calificacion_display',
            'fecha_cierre', 'observaciones_generales',
        ]
        read_only_fields = ['id', 'fecha_cierre', 'promedio', 'calificacion_final']


class InvitacionSerializer(serializers.ModelSerializer):
    instructor_nombre = serializers.CharField(source='instructor.username', read_only=True)
    invitado_nombre   = serializers.CharField(source='instructor_invitado.username', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    instructores_jurados_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Usuario.objects.filter(rol=Rol.INSTRUCTOR),
        source='instructores_jurados', write_only=True, required=False
    )
    ficha_numero = serializers.CharField(source='ficha.numero', read_only=True)
    jurados_nombres = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Invitacion
        fields = [
            'id', 'instructor', 'instructor_nombre', 'instructor_invitado',
            'invitado_nombre', 'ficha', 'ficha_numero', 'estado', 'estado_display',
            'instructores_jurados', 'instructores_jurados_ids', 'jurados_nombres',
            'fecha_envio', 'fecha_respuesta', 'fecha_evaluacion',
            'hora_evaluacion', 'mensaje',
        ]
        read_only_fields = ['id', 'fecha_envio']

    def get_jurados_nombres(self, obj):
        return [{'id': u.id, 'nombre': f"{u.first_name} {u.last_name}".strip() or u.username}
                for u in obj.instructores_jurados.all()]


class ChecklistSerializer(serializers.ModelSerializer):
    cantidad_items = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = Checklist
        fields = [
            'id', 'titulo', 'descripcion', 'activo',
            'cantidad_items', 'created_at', 'updated_at',
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
