from django.http import HttpResponse


def home(request):
    return HttpResponse('Aprendices app (Etapa 2 - esqueleto).')

