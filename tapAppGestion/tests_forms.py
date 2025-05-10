import json
from datetime import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils.timezone import now
from tapAppGestion.forms import (
    ProductoForm, RegistroForm, EditProfileForm,
    PedidoForm, ActualizarStockForm, RegistroHorarioForm
)
from tapAppGestion.models import Producto, Pedido, PedidoProducto, RegistroHorario

class ProductoFormTests(TestCase):
    def test_producto_form_valid(self):
        data = {'nombre': 'Test', 'categoria': 'Cafés', 'precio': '1.23'}
        form = ProductoForm(data)
        self.assertTrue(form.is_valid())
        prod = form.save()
        self.assertEqual(prod.nombre, 'Test')
        self.assertEqual(prod.categoria, 'Cafés')
        self.assertEqual(prod.precio, Decimal('1.23'))

    def test_producto_form_missing_fields(self):
        form = ProductoForm({})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('categoria', form.errors)
        self.assertIn('precio', form.errors)

class RegistroFormTests(TestCase):
    def setUp(self):
        User.objects.create_user(username='u1', email='dup@example.com', password='Xx1234!')

    def test_registro_form_valid(self):
        data = {
            'username': 'tester',
            'email': 'test@example.com',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'password1': 'P4$wigXqZL',
            'password2': 'P4$wigXqZL',
        }
        form = RegistroForm(data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_registro_form_duplicate_email(self):
        data = {
            'username':'tester2','email':'dup@example.com',
            'first_name':'N','last_name':'A',
            'password1':'secret','password2':'secret'
        }
        form = RegistroForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(form.errors['email'], ["Este correo ya está registrado."])

    def test_registro_form_password_mismatch(self):
        data = {
            'username':'u3','email':'u3@example.com',
            'first_name':'N','last_name':'A',
            'password1':'a','password2':'b'
        }
        form = RegistroForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

class EditProfileFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='u1', email='u1@example.com', password='x',
            first_name='A', last_name='B'
        )

    def test_edit_profile_form_valid_no_password(self):
        data = {'first_name':'X','last_name':'Y','email':'new@example.com',
                'password1':'','password2':''}
        form = EditProfileForm(data, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.first_name, 'X')
        self.assertEqual(user.email, 'new@example.com')
        self.assertTrue(user.check_password('x'))

    def test_edit_profile_form_password_change(self):
        data = {'first_name':'A','last_name':'B','email':'u1@example.com',
                'password1':'newpass','password2':'newpass'}
        form = EditProfileForm(data, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.check_password('newpass'))

    def test_edit_profile_form_password_mismatch(self):
        data = {'first_name':'A','last_name':'B','email':'u1@example.com',
                'password1':'x1','password2':'x2'}
        form = EditProfileForm(data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn('Las contraseñas no coinciden.', form.errors['__all__'])

class PedidoFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', password='pass')
        self.p1 = Producto.objects.create(nombre='P1', categoria='A', precio=Decimal('1.00'))
        self.p2 = Producto.objects.create(nombre='P2', categoria='B', precio=Decimal('2.00'))

    def test_pedido_form_valid_and_save_raises(self):
        cantidades = {str(self.p1.id): 3, str(self.p2.id): 5}
        data = {
            'mesa': '5',
            'numero_clientes': 2,
            'productos': [self.p1.id, self.p2.id],
            'cantidades': json.dumps(cantidades),
        }
        form = PedidoForm(data)
        self.assertTrue(form.is_valid(), form.errors)

        form.instance.camarero = self.user
        with self.assertRaises(NameError):
            form.save()

    def test_pedido_form_missing_productos(self):
        data = {'mesa': '1', 'numero_clientes': 1, 'productos': []}
        form = PedidoForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('productos', form.errors)

class ActualizarStockFormTests(TestCase):
    def test_actualizar_stock_form_valid(self):
        prod = Producto.objects.create(
            nombre='X', categoria='Cat', precio=Decimal('1.00'),
            cantidad=10
        )
        form = ActualizarStockForm({'cantidad': 7}, instance=prod)
        self.assertTrue(form.is_valid(), form.errors)
        prod2 = form.save()
        self.assertEqual(prod2.cantidad, 7)

    def test_actualizar_stock_form_invalid(self):
        form = ActualizarStockForm({'cantidad': ''}, instance=Producto(cantidad=1))
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad', form.errors)

class RegistroHorarioFormTests(TestCase):
    def test_registrohorario_form_valid(self):
        data = {
            'hora_entrada': now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        form = RegistroHorarioForm(data)
        self.assertTrue(form.is_valid())

    def test_registrohorario_form_blank_salida(self):
        data = {'hora_entrada': now().strftime('%Y-%m-%d %H:%M:%S')}
        form = RegistroHorarioForm(data)
        self.assertTrue(form.is_valid(), form.errors)
