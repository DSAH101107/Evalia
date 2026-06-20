from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.evaluacion.models import Aprendiz, Ficha, Fase, GAES, Evaluacion, Checklist

Usuario = get_user_model()


class UsuarioModelTest(TestCase):
    def test_creacion_usuario_admin(self):
        user = Usuario.objects.create_user(username='admin1', password='test123')
        self.assertEqual(user.rol, 'instructor')

    def test_superuser_tiene_rol_admin(self):
        user = Usuario.objects.create_superuser(username='superadmin', password='test123')
        self.assertEqual(user.rol, 'administrador')
        self.assertTrue(user.is_superuser)


class AprendizModelTest(TestCase):
    def setUp(self):
        self.gaes = GAES.objects.create(nombre='GAES 1', descripcion='GAE de prueba')
        self.fase = Fase.objects.create(numero=1, nombre='Fase 1')
        self.ficha = Ficha.objects.create(numero='12345')

    def test_creacion_aprendiz(self):
        aprendiz = Aprendiz.objects.create(
            documento='12345678',
            nombres='Juan',
            apellidos='Perez',
            email='juan@test.com',
            ficha=self.ficha,
            gaes=self.gaes,
            fase=self.fase
        )
        self.assertIn('Juan Perez', str(aprendiz))

    def test_aprendiz_bloqueado(self):
        aprendiz = Aprendiz.objects.create(
            documento='87654321',
            nombres='Maria',
            apellidos='Gomez',
            email='maria@test.com',
            ficha=self.ficha,
            gaes=self.gaes,
            fase=self.fase,
            bloqueado=True
        )
        self.assertIn('Maria Gomez', str(aprendiz))


class LoginRedirectTest(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin', password='test123')
        self.admin.rol = 'administrador'
        self.admin.save()

    def test_login_valido_redirige_admin(self):
        response = self.client.post('/usuarios/login/', {
            'username': 'admin',
            'password': 'test123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)