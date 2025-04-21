from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Producto
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user


class IndexViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.url = reverse('index') 

    def test_index_redirects_if_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url) 

    def test_index_renders_for_logged_in_user(self):
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

class AgregarProductoViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.client.login(username='tester', password='test1234')
        self.url = reverse('agregar_producto')

    def test_agregar_producto_post_valido(self):
        data = {
            'nombre': 'Producto Test',
            'categoria': 'Cervezas',
            'precio': '3.50',
        }

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('menu'))
        self.assertTrue(Producto.objects.filter(nombre='Producto Test').exists())


