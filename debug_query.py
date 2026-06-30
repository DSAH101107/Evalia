import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from apps.evaluacion.models import Resultado, Evaluacion, EvaluacionItem

eval_count = Evaluacion.objects.count()
eval_cancelada = Evaluacion.objects.filter(estado=Evaluacion.ESTADO_CANCELADA).count()
item_count = EvaluacionItem.objects.count()
result_count = Resultado.objects.count()

print(f'Evaluaciones totales: {eval_count}')
print(f'Evaluaciones canceladas: {eval_cancelada}')
print(f'EvaluacionItems totales: {item_count}')
print(f'Resultados totales: {result_count}')
