from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Producto, Pedido, PedidoProducto, RegistroHorario, ProductoPagado
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user
from tapAppGestion.forms import RegistroForm, EditProfileForm, ProductoForm, PedidoForm
from django.contrib.messages import get_messages
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
import json
import io
from xhtml2pdf import pisa
from io import BytesIO
from unittest.mock import patch
from django.utils.timezone import localtime, now

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

class SalirViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.url = reverse('salir')

    def test_salir_redirects_to_index_when_logged_in(self):
        """GET /salir/ con usuario logueado redirige a 'index'."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        # Sólo comprobamos la primera redirección, no seguimos hasta el login
        self.assertRedirects(
            response,
            reverse('index'),
            fetch_redirect_response=False
        )

    def test_salir_logs_out_user(self):
        """Tras llamar a /salir/, la sesión no contiene _auth_user_id."""
        self.client.login(username='tester', password='test1234')
        self.client.get(self.url)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_salir_redirects_to_index_when_anonymous(self):
        """GET /salir/ sin autenticación redirige a 'index'."""
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            reverse('index'),
            fetch_redirect_response=False
        )

    def test_salir_via_post_also_works(self):
        """POST a /salir/ redirige a 'index' y cierra la sesión."""
        self.client.login(username='tester', password='test1234')
        response = self.client.post(self.url, {})
        self.assertRedirects(
            response,
            reverse('index'),
            fetch_redirect_response=False
        )
        self.assertNotIn('_auth_user_id', self.client.session)

class RegistroViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def test_get_shows_empty_form(self):
        """GET a /register/ debe devolver el formulario vacío."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')
        # Comprobamos que en el contexto viene una instancia de RegistroForm
        self.assertIsInstance(response.context['form'], RegistroForm)

    def test_post_valid_registration_creates_user_and_redirects(self):
        """POST válido crea usuario, añade mensaje de éxito y redirige a profile."""
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'password1': 'ComplexPass123',
            'password2': 'ComplexPass123',
        }
        response = self.client.post(self.url, data)
        # Sólo comprobamos la primera redirección a 'profile'
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        # Usuario creado
        self.assertTrue(User.objects.filter(username='newuser', email='new@example.com').exists())
        # Mensaje de éxito presente
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Tu cuenta ha sido creada" in m.message for m in msgs))

    def test_post_invalid_registration_shows_errors(self):
        """POST inválido (contraseñas distintas) vuelve a renderizar con errores y no crea usuario."""
        data = {
            'username': 'user2',
            'email': 'u2@example.com',
            'first_name': 'Nombre2',
            'last_name': 'Apellido2',
            'password1': 'pass1234',
            'password2': 'diffpass',
        }
        response = self.client.post(self.url, data)
        # No redirige, muestra de nuevo el template
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')
        # Usuario NO creado
        self.assertFalse(User.objects.filter(username='user2').exists())
        # El formulario tiene errores en password2
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('password2', form.errors)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('profile')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')

    def test_redirect_if_not_logged_in(self):
        """GET a /profile/ sin autenticarse redirige al login con next."""
        response = self.client.get(self.url)
        expected_redirect = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)

    def test_profile_renders_for_logged_in_user(self):
        """GET a /profile/ con usuario autenticado devuelve profile.html y contexto."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')
        # El contexto 'user' debe ser el mismo usuario de la sesión
        self.assertIn('user', response.context)
        self.assertEqual(response.context['user'].username, 'tester')


class PersonalViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('personal')
        # Creamos varios usuarios de prueba
        self.user1 = User.objects.create_user(username='user1', password='pass1')
        self.user2 = User.objects.create_user(username='user2', password='pass2')

    def test_personal_view_accessible_to_anyone(self):
        """La vista personal/ debe responder 200 y usar el template correcto."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'personal.html')

    def test_personal_view_context_contains_all_users(self):
        """El contexto 'usuarios' debe incluir todos los usuarios de la BD."""
        response = self.client.get(self.url)
        usuarios = response.context['usuarios']
        # Convertimos a lista para comparar
        self.assertEqual(list(usuarios.order_by('id')), list(User.objects.all().order_by('id')))
        # Además comprobamos que los usuarios creados estén en la lista
        self.assertIn(self.user1, usuarios)
        self.assertIn(self.user2, usuarios)


class EditProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('editar_perfil')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            username='tester', password='oldpass',
            first_name='Old', last_name='Name', email='old@example.com'
        )

    def test_redirect_if_not_logged_in(self):
        """GET /editar_perfil/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_renders_form_with_instance(self):
        """GET con sesión muestra formulario pre-llenado."""
        self.client.login(username='tester', password='oldpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'edit_profile.html')
        form = response.context['form']
        self.assertIsInstance(form, EditProfileForm)
        self.assertEqual(form.instance, self.user)

    def test_post_update_profile_without_password(self):
        """POST válido sin contraseña cambia datos, deja sesión viva y avisa."""
        self.client.login(username='tester', password='oldpass')
        data = {
            'first_name': 'NewFirst',
            'last_name': 'NewLast',
            'email': 'new@example.com',
            'password1': '',
            'password2': '',
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('index'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NewFirst')
        self.assertEqual(self.user.email, 'new@example.com')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Tu perfil ha sido actualizado correctamente." in m.message for m in msgs))
        # La sesión sigue activa
        profile_resp = self.client.get(reverse('profile'))
        self.assertEqual(profile_resp.status_code, 200)

    def test_post_change_password(self):
        """POST con nueva contraseña actualiza pwd, mantiene sesión y avisa."""
        self.client.login(username='tester', password='oldpass')
        data = {
            'first_name': 'Old',
            'last_name': 'Name',
            'email': 'old@example.com',
            'password1': 'newpass123',
            'password2': 'newpass123',
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('index'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Tu contraseña ha sido actualizada correctamente." in m.message for m in msgs))
        profile_resp = self.client.get(reverse('profile'))
        self.assertEqual(profile_resp.status_code, 200)

    def test_post_mismatched_passwords_shows_error(self):
        """POST con passwords diferentes no redirige, muestra error y no salva."""
        self.client.login(username='tester', password='oldpass')
        data = {
            'first_name': 'X',
            'last_name': 'Y',
            'email': 'xy@example.com',
            'password1': 'abc',
            'password2': 'def',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'edit_profile.html')
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('__all__', form.errors)
        # Asegúrate de que tu form incluya un error global adecuado para contraseñas desiguales
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.com')
        self.assertTrue(self.user.check_password('oldpass'))

class DeleteUserViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Usuario que realizará la acción (debe estar autenticado)
        self.admin_user = User.objects.create_user(username='admin', password='adminpass')
        # Usuario objetivo a eliminar
        self.target_user = User.objects.create_user(username='todelete', password='pass123')
        self.url = reverse('delete_user', args=[self.target_user.id])
        self.login_url = reverse('login')
        self.personal_url = reverse('personal')

    def test_redirect_if_not_logged_in(self):
        """GET a /delete_user/<id>/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_renders_confirmation_template(self):
        """GET con sesión muestra confirm_delete.html con el usuario en contexto."""
        self.client.login(username='admin', password='adminpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'confirm_delete.html')
        self.assertIn('user', response.context)
        self.assertEqual(response.context['user'], self.target_user)

    def test_post_deletes_user_and_redirects(self):
        """POST elimina el usuario, añade mensaje y redirige a 'personal'."""
        self.client.login(username='admin', password='adminpass')
        response = self.client.post(self.url, {})
        # Comprueba redirección inicial a personal
        self.assertRedirects(response, self.personal_url, fetch_redirect_response=False)
        # El usuario ya no existe
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())
        # Mensaje de éxito presente
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("El usuario ha sido eliminado." in m.message for m in msgs))

    def test_post_does_not_delete_on_get(self):
        """GET no elimina el usuario."""
        self.client.login(username='admin', password='adminpass')
        _ = self.client.get(self.url)
        self.assertTrue(User.objects.filter(id=self.target_user.id).exists())

    def test_post_nonexistent_user_returns_404(self):
        """Acceder a un ID inexistente devuelve 404."""
        self.client.login(username='admin', password='adminpass')
        url = reverse('delete_user', args=[9999])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)

class MenuViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('menu')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')

    def test_redirect_if_not_logged_in(self):
        """GET /menu/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_no_products_returns_empty_categories(self):
        """Si no hay productos, el contexto 'categorias' está vacío."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'menu.html')
        categorias = response.context['categorias']
        self.assertIsInstance(categorias, dict)
        self.assertFalse(categorias)

    def test_products_grouped_by_category(self):
        """Productos se agrupan correctamente por su campo 'categoria'."""
        self.client.login(username='tester', password='test1234')
        # Creamos productos en dos categorías distintas
        p1 = Producto.objects.create(nombre='Beer1', categoria='Cervezas', precio=2.5)
        p2 = Producto.objects.create(nombre='Beer2', categoria='Cervezas', precio=3.0)
        p3 = Producto.objects.create(nombre='Tapas1', categoria='Tapas', precio=5.0)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        categorias = response.context['categorias']

        # Debe haber exactamente dos claves: 'Cervezas' y 'Tapas'
        self.assertCountEqual(categorias.keys(), ['Cervezas', 'Tapas'])

        # Los productos aparecen en la lista correcta
        self.assertIn(p1, categorias['Cervezas'])
        self.assertIn(p2, categorias['Cervezas'])
        self.assertIn(p3, categorias['Tapas'])

        # Comprobamos número de elementos por categoría
        self.assertEqual(len(categorias['Cervezas']), 2)
        self.assertEqual(len(categorias['Tapas']), 1)

class ProductoDetalleViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        # Creamos un usuario y un producto de prueba
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.producto = Producto.objects.create(nombre='TestProd', categoria='Test', precio=1.23)
        self.url = reverse('producto_detalle', args=[self.producto.id])

    def test_redirect_if_not_logged_in(self):
        """GET a /producto/<id>/ sin autenticar redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_renders_detail_for_logged_in_user(self):
        """GET a /producto/<id>/ con usuario autenticado muestra detalle."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'producto_detalle.html')
        # Contexto contiene el producto correcto
        self.assertEqual(response.context['producto'], self.producto)

    def test_invalid_product_id_returns_404(self):
        """GET con un producto_id que no existe devuelve 404."""
        self.client.login(username='tester', password='test1234')
        bad_url = reverse('producto_detalle', args=[9999])
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

class EditarProductoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = lambda pk: reverse('editar_producto', args=[pk])
        self.menu_url = reverse('menu')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='user', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')
        self.producto = Producto.objects.create(
            nombre='Antiguo', categoria='Cervezas', precio='4.00'
        )

    def test_redirect_if_not_logged_in(self):
        """GET sin login redirige al login con next."""
        response = self.client.get(self.url(self.producto.id))
        expected = f"{self.login_url}?next={self.url(self.producto.id)}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_permission_denied_for_non_superuser(self):
        """Usuario no superuser recibe 403."""
        self.client.login(username='user', password='pass')
        response = self.client.get(self.url(self.producto.id))
        self.assertEqual(response.status_code, 403)

    def test_get_renders_form_for_superuser(self):
        """GET con superuser muestra form con instancia."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url(self.producto.id))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'editar_producto.html')
        form = response.context['form']
        self.assertIsInstance(form, ProductoForm)
        self.assertEqual(form.instance, self.producto)
        self.assertEqual(response.context['producto'], self.producto)

    def test_post_valid_updates_and_redirects(self):
        """POST válido con superuser actualiza y redirige a menu."""
        self.client.login(username='admin', password='pass')
        data = {
            'nombre': 'NuevoNombre',
            'categoria': 'Tapas o ½ Ración',
            'precio': '5.50',
        }
        response = self.client.post(self.url(self.producto.id), data)
        self.assertRedirects(response, self.menu_url, fetch_redirect_response=False)
        # Verificar cambios en la BD
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'NuevoNombre')
        self.assertEqual(str(self.producto.precio), '5.50')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("El producto ha sido actualizado." in m.message for m in msgs))

    def test_post_invalid_shows_errors_and_does_not_change(self):
        """POST inválido re-renderiza con errores y no modifica el producto."""
        self.client.login(username='admin', password='pass')
        data = {
            'nombre': '',  # requerido
            'categoria': 'Cervezas',
            'precio': '',
        }
        old_nombre = self.producto.nombre
        old_precio = str(self.producto.precio) 

        response = self.client.post(self.url(self.producto.id), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'editar_producto.html')
        form = response.context['form']
        self.assertTrue(form.errors)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, old_nombre)
        self.assertEqual(str(self.producto.precio), old_precio)

class EliminarProductoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = lambda pk: reverse('eliminar_producto', args=[pk])
        self.menu_url = reverse('menu')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='user', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')
        self.producto = Producto.objects.create(
            nombre='A eliminar', categoria='Tapas', precio='2.00'
        )

    def test_redirect_if_not_logged_in(self):
        """GET sin login redirige al login con next."""
        response = self.client.get(self.url(self.producto.id))
        expected = f"{self.login_url}?next={self.url(self.producto.id)}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_permission_denied_for_non_superuser(self):
        """Usuario no superuser recibe 403."""
        self.client.login(username='user', password='pass')
        response = self.client.get(self.url(self.producto.id))
        self.assertEqual(response.status_code, 403)

    def test_get_renders_confirmation_for_superuser(self):
        """GET con superuser muestra plantilla de confirmación."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url(self.producto.id))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'confirmacion_eliminar_producto.html')
        self.assertEqual(response.context['producto'], self.producto)

    def test_get_does_not_delete(self):
        """GET no elimina el producto."""
        self.client.login(username='admin', password='pass')
        _ = self.client.get(self.url(self.producto.id))
        self.assertTrue(Producto.objects.filter(id=self.producto.id).exists())

    def test_post_deletes_and_redirects(self):
        """POST con superuser elimina producto, añade mensaje y redirige."""
        self.client.login(username='admin', password='pass')
        response = self.client.post(self.url(self.producto.id), {})
        # Comprueba redirección inicial a menu
        self.assertRedirects(response, self.menu_url, fetch_redirect_response=False)
        # Producto eliminado
        self.assertFalse(Producto.objects.filter(id=self.producto.id).exists())
        # Mensaje de éxito presente
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("El producto ha sido eliminado." in m.message for m in msgs))

    def test_nonexistent_product_returns_404(self):
        """GET o POST sobre ID inexistente devuelve 404."""
        self.client.login(username='admin', password='pass')
        bad_url = self.url(9999)
        response_get = self.client.get(bad_url)
        response_post = self.client.post(bad_url, {})
        self.assertEqual(response_get.status_code, 404)
        self.assertEqual(response_post.status_code, 404)

class ListaPedidosViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        self.list_url = reverse('lista_pedidos')
        self.list_confirm_url = lambda pid: reverse('lista_pedidos_confirmado', args=[pid])

    def test_redirect_if_not_logged_in(self):
        """GET /pedidos/ sin login redirige al login con next."""
        response = self.client.get(self.list_url)
        expected = f"{self.login_url}?next={self.list_url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_no_pedidos_returns_empty_list(self):
        """Si no hay pedidos pendientes, context['pedidos_con_productos'] es [] y pedido_reciente_id None."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lista_pedidos.html')
        cp = response.context['pedidos_con_productos']
        self.assertIsInstance(cp, list)
        self.assertFalse(cp)
        self.assertIsNone(response.context['pedido_reciente_id'])

    def test_excludes_paid_pedidos_and_groups_totals_ordered(self):
        """Sólo aparecen pedidos no pagados, agrupados por fecha descendente con su total."""
        self.client.login(username='tester', password='test1234')
        # Productos
        prod1 = Producto.objects.create(nombre='P1', categoria='A', precio='2.50')
        prod2 = Producto.objects.create(nombre='P2', categoria='B', precio='3.00')
        # Pedidos: uno reciente, otro antiguo y uno pagado
        now = timezone.now()
        pedido_old = Pedido.objects.create(
            mesa='1', numero_clientes=2, camarero=self.user,
            pagado=False, fecha=now - timedelta(days=1)
        )
        pedido_new = Pedido.objects.create(
            mesa='2', numero_clientes=3, camarero=self.user,
            pagado=False, fecha=now
        )
        Pedido.objects.create(
            mesa='X', numero_clientes=1, camarero=self.user,
            pagado=True, fecha=now + timedelta(hours=1)
        )
        # Asociar cantidades
        PedidoProducto.objects.create(pedido=pedido_old, producto=prod2, cantidad=1)
        PedidoProducto.objects.create(pedido=pedido_new, producto=prod1, cantidad=2)

        response = self.client.get(self.list_url)
        cp = response.context['pedidos_con_productos']

        # Sólo los dos no pagados, en orden descendente de fecha
        self.assertEqual(len(cp), 2)
        self.assertEqual(cp[0]['pedido'], pedido_new)
        self.assertEqual(cp[1]['pedido'], pedido_old)

        # Totales calculados correctamente como floats
        tot_new = round(float(prod1.precio) * 2, 2)
        tot_old = round(float(prod2.precio) * 1, 2)
        self.assertEqual(cp[0]['total_pedido'], tot_new)
        self.assertEqual(cp[1]['total_pedido'], tot_old)

class ListaPedidosCerradosViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        self.url = reverse('lista_pedidos_cerrados')

        now = timezone.now()
        # Productos con precios diferentes
        self.prod1 = Producto.objects.create(nombre='P1', categoria='A', precio='1.00')
        self.prod2 = Producto.objects.create(nombre='P2', categoria='B', precio='2.00')
        self.prod3 = Producto.objects.create(nombre='P3', categoria='C', precio='3.00')
        self.prod4 = Producto.objects.create(nombre='P4', categoria='D', precio='4.00')

        # Pedidos pagados con fecha_cierre variable
        self.p_recent = Pedido.objects.create(
            mesa='1', numero_clientes=1, camarero=self.user,
            pagado=True, fecha_cierre=now - timedelta(days=1)
        )
        self.p_week_old = Pedido.objects.create(
            mesa='2', numero_clientes=2, camarero=self.user,
            pagado=True, fecha_cierre=now - timedelta(days=8)
        )
        self.p_month_old = Pedido.objects.create(
            mesa='3', numero_clientes=3, camarero=self.user,
            pagado=True, fecha_cierre=now - timedelta(days=31)
        )
        self.p_year_old = Pedido.objects.create(
            mesa='4', numero_clientes=4, camarero=self.user,
            pagado=True, fecha_cierre=now - timedelta(days=366)
        )
        # Pedido no pagado (debe excluirse siempre)
        Pedido.objects.create(
            mesa='X', numero_clientes=5, camarero=self.user,
            pagado=False, fecha_cierre=now
        )

        # Asignar un producto a cada pedido (cantidad=1)
        PedidoProducto.objects.create(pedido=self.p_recent, producto=self.prod1, cantidad=1)
        PedidoProducto.objects.create(pedido=self.p_week_old, producto=self.prod2, cantidad=1)
        PedidoProducto.objects.create(pedido=self.p_month_old, producto=self.prod3, cantidad=1)
        PedidoProducto.objects.create(pedido=self.p_year_old, producto=self.prod4, cantidad=1)

    def test_redirect_if_not_logged_in(self):
        """GET /lista_pedidos_cerrados/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_default_recientes_shows_all_paid_orders(self):
        """Sin filtro explícito, aparecen todos los pedidos pagados en orden descendente."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        cp = response.context['pedidos_con_precio']
        # Debe incluir exactamente 4 pedidos pagados
        self.assertEqual(len(cp), 4)
        # Orden descendente por fecha_cierre: primero el más reciente
        self.assertEqual(cp[0]['pedido'], self.p_recent)
        self.assertEqual(cp[-1]['pedido'], self.p_year_old)
        # Totales según precio*1
        expected_totals = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual([item['total_pedido'] for item in cp], expected_totals)
        # Filtro actual por defecto
        self.assertEqual(response.context['filtro_actual'], 'recientes')

    def test_filter_ultima_semana(self):
        """Con filtro=ultima_semana, sólo pedidos con fecha_cierre >= hace 7 días."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url, {'filtro': 'ultima_semana'})
        cp = response.context['pedidos_con_precio']
        self.assertEqual(len(cp), 1)
        self.assertEqual(cp[0]['pedido'], self.p_recent)
        self.assertEqual(response.context['filtro_actual'], 'ultima_semana')

    def test_filter_ultimo_mes(self):
        """Con filtro=ultimo_mes, pedidos en los últimos 30 días."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url, {'filtro': 'ultimo_mes'})
        cp = response.context['pedidos_con_precio']
        self.assertCountEqual([item['pedido'] for item in cp], [self.p_recent, self.p_week_old])
        self.assertEqual(response.context['filtro_actual'], 'ultimo_mes')

    def test_filter_ultimo_ano(self):
        """Con filtro=ultimo_ano, pedidos en los últimos 365 días."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url, {'filtro': 'ultimo_ano'})
        cp = response.context['pedidos_con_precio']
        self.assertCountEqual([item['pedido'] for item in cp],
                              [self.p_recent, self.p_week_old, self.p_month_old])
        self.assertEqual(response.context['filtro_actual'], 'ultimo_ano')

    def test_filter_por_fecha(self):
        """Con filtro=por_fecha y rango, filtra por fecha_cierre__date__range."""
        self.client.login(username='tester', password='test1234')
        inicio = (self.p_week_old.fecha_cierre.date()).isoformat()
        fin = (self.p_recent.fecha_cierre.date()).isoformat()
        response = self.client.get(self.url, {
            'filtro': 'por_fecha',
            'fecha_inicio': inicio,
            'fecha_fin': fin
        })
        cp = response.context['pedidos_con_precio']
        self.assertCountEqual([item['pedido'] for item in cp], [self.p_recent, self.p_week_old])
        self.assertEqual(response.context['filtro_actual'], 'por_fecha')

    def test_filter_por_mes(self):
        """Con filtro=por_mes y mes=YYYY-MM, filtra por año y mes."""
        self.client.login(username='tester', password='test1234')
        mes = self.p_recent.fecha_cierre.strftime('%Y-%m')
        response = self.client.get(self.url, {'filtro': 'por_mes', 'mes': mes})
        cp = response.context['pedidos_con_precio']
        expected = [self.p_recent, self.p_week_old]
        self.assertCountEqual([item['pedido'] for item in cp], expected)
        self.assertEqual(response.context['filtro_actual'], 'por_mes')

    def test_filter_por_dia(self):
        """Con filtro=por_dia y día concreto, filtra por fecha_cierre__date exacto."""
        self.client.login(username='tester', password='test1234')
        dia = self.p_week_old.fecha_cierre.date().isoformat()
        response = self.client.get(self.url, {'filtro': 'por_dia', 'dia': dia})
        cp = response.context['pedidos_con_precio']
        self.assertEqual(len(cp), 1)
        self.assertEqual(cp[0]['pedido'], self.p_week_old)
        self.assertEqual(response.context['filtro_actual'], 'por_dia')

class DetallesPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')

        # Creamos un pedido y algunos productos
        self.pedido = Pedido.objects.create(
            mesa='1', numero_clientes=2, camarero=self.user,
            pagado=False
        )
        self.prod1 = Producto.objects.create(nombre='Prod1', categoria='A', precio='2.50')
        self.prod2 = Producto.objects.create(nombre='Prod2', categoria='B', precio='3.00')

        # Asociamos cantidades
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.prod1, cantidad=1)
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.prod2, cantidad=2)

        self.url = reverse('detalles_pedido', args=[self.pedido.id])

    def test_redirect_if_not_logged_in(self):
        """GET /pedidos/<id>/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_renders_detail_for_logged_in_user(self):
        """GET con sesión muestra template, pedido, productos y total correcto."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'detalles_pedido.html')

        # Contexto contiene el pedido
        self.assertEqual(response.context['pedido'], self.pedido)

        # Contexto productos_pedido incluye las relaciones correctas
        productos_qs = response.context['productos_pedido']
        self.assertEqual(list(productos_qs), list(PedidoProducto.objects.filter(pedido=self.pedido)))

        # Total = 1*2.50 + 2*3.00 = 2.50 + 6.00 = 8.50
        self.assertEqual(response.context['total_pedido'], 8.50)

    def test_nonexistent_pedido_returns_404(self):
        """GET con pedido_id inválido devuelve 404."""
        self.client.login(username='tester', password='test1234')
        bad_url = reverse('detalles_pedido', args=[9999])
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

    def test_no_products_total_zero(self):
        """Si el pedido no tiene productos, total_pedido es 0.0."""
        # Creamos un nuevo pedido sin productos
        pedido2 = Pedido.objects.create(
            mesa='2', numero_clientes=1, camarero=self.user,
            pagado=False
        )
        url2 = reverse('detalles_pedido', args=[pedido2.id])
        self.client.login(username='tester', password='test1234')
        response = self.client.get(url2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['productos_pedido']), [])
        self.assertEqual(response.context['total_pedido'], 0.0)

class DetallePedidoCerradoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')

        # Creamos un pedido abierto y otro cerrado
        now = timezone.now()
        self.pedido_open = Pedido.objects.create(
            mesa='A', numero_clientes=1, camarero=self.user,
            pagado=False, fecha_cierre=now
        )
        self.pedido_closed = Pedido.objects.create(
            mesa='B', numero_clientes=2, camarero=self.user,
            pagado=True, fecha_cierre=now - timedelta(hours=1)
        )

        # Productos para el pedido cerrado
        self.prod1 = Producto.objects.create(nombre='Prod1', categoria='X', precio='1.50')
        self.prod2 = Producto.objects.create(nombre='Prod2', categoria='Y', precio='2.00')

        # Asociamos cantidades al pedido cerrado
        PedidoProducto.objects.create(pedido=self.pedido_closed, producto=self.prod1, cantidad=2)
        PedidoProducto.objects.create(pedido=self.pedido_closed, producto=self.prod2, cantidad=1)

        self.url_closed = reverse('detalle_pedido_cerrado', args=[self.pedido_closed.id])
        self.url_open = reverse('detalle_pedido_cerrado', args=[self.pedido_open.id])
        self.url_nonexistent = reverse('detalle_pedido_cerrado', args=[9999])

    def test_redirect_if_not_logged_in(self):
        """GET /pedido_cerrado/<id>/ sin login redirige al login con next."""
        response = self.client.get(self.url_closed)
        expected = f"{self.login_url}?next={self.url_closed}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_nonexistent_or_open_order_returns_404(self):
        """GET con ID inexistente o pedido no pagado devuelve 404."""
        self.client.login(username='tester', password='test1234')
        response_nonexistent = self.client.get(self.url_nonexistent)
        response_open = self.client.get(self.url_open)
        self.assertEqual(response_nonexistent.status_code, 404)
        self.assertEqual(response_open.status_code, 404)

    def test_renders_closed_order_details(self):
        """GET con pedido cerrado muestra template y contexto correcto."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url_closed)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'detalles_pedido_cerrado.html')

        # Contexto contiene el pedido cerrado
        self.assertEqual(response.context['pedido'], self.pedido_closed)

        # Contexto productos_pedido incluye las líneas correctas
        qs = response.context['productos_pedido']
        self.assertCountEqual(
            list(qs),
            list(PedidoProducto.objects.filter(pedido=self.pedido_closed))
        )

        # Total = 2 * 1.50 + 1 * 2.00 = 3.00 + 2.00 = 5.00
        self.assertEqual(response.context['total_pedido'], Decimal('5.00'))

    def test_no_products_total_zero(self):
        """Si un pedido cerrado no tiene productos, total_pedido es 0.00."""
        # Creamos un pedido cerrado sin líneas de productos
        pedido_empty = Pedido.objects.create(
            mesa='C', numero_clientes=3, camarero=self.user,
            pagado=True, fecha_cierre=timezone.now()
        )
        url_empty = reverse('detalle_pedido_cerrado', args=[pedido_empty.id])
        self.client.login(username='tester', password='test1234')
        response = self.client.get(url_empty)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['productos_pedido']), [])
        self.assertEqual(response.context['total_pedido'], Decimal('0.00'))

class EliminarPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        # Creamos un pedido de prueba
        self.pedido = Pedido.objects.create(
            mesa='10', numero_clientes=2, camarero=self.user, pagado=False
        )
        self.url = reverse('eliminar_pedido', args=[self.pedido.id])
        self.list_url = reverse('lista_pedidos')

    def test_redirect_if_not_logged_in(self):
        """GET /eliminar_pedido/<id>/ sin login redirige a login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_renders_confirmation_template(self):
        """GET con sesión muestra confirmacion_eliminar_pedido.html y contexto."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'confirmacion_eliminar_pedido.html')
        self.assertIn('pedido', response.context)
        self.assertEqual(response.context['pedido'], self.pedido)

    def test_get_does_not_delete_pedido(self):
        """GET no elimina el pedido."""
        self.client.login(username='tester', password='test1234')
        _ = self.client.get(self.url)
        self.assertTrue(Pedido.objects.filter(id=self.pedido.id).exists())

    def test_post_deletes_and_redirects(self):
        """POST elimina el pedido y redirige a lista_pedidos."""
        self.client.login(username='tester', password='test1234')
        response = self.client.post(self.url, {})
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        self.assertFalse(Pedido.objects.filter(id=self.pedido.id).exists())

    def test_nonexistent_pedido_returns_404(self):
        """GET o POST sobre ID inexistente devuelve 404."""
        self.client.login(username='tester', password='test1234')
        bad_url = reverse('eliminar_pedido', args=[9999])
        response_get = self.client.get(bad_url)
        response_post = self.client.post(bad_url, {})
        self.assertEqual(response_get.status_code, 404)
        self.assertEqual(response_post.status_code, 404)

class EditarPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        self.url = lambda pk: reverse('editar_pedido', args=[pk])
        self.list_url = reverse('lista_pedidos')

        # Dos productos en distintas categorías
        self.prod1 = Producto.objects.create(
            nombre='ProdA', categoria='Cervezas', precio=Decimal('1.00'),
            kilos_disponibles=Decimal('0.016')
        )
        self.prod2 = Producto.objects.create(
            nombre='ProdB', categoria='Tapas o ½ Ración', precio=Decimal('2.00')
        )

        # Pedido inicial con un producto asociado
        self.pedido = Pedido.objects.create(
            mesa='M1', numero_clientes=2, camarero=self.user, pagado=False
        )
        PedidoProducto.objects.create(
            pedido=self.pedido, producto=self.prod1, cantidad=3
        )

    def test_redirect_if_not_logged_in(self):
        """GET /editar_pedido/ sin login redirige al login con next."""
        response = self.client.get(self.url(self.pedido.id))
        expected = f"{self.login_url}?next={self.url(self.pedido.id)}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_prefills_form_and_context(self):
        """GET autenticado muestra crear_pedido.html con form, categorías y seleccionados."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url(self.pedido.id))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crear_pedido.html')
        form = response.context['form']
        self.assertIsInstance(form, PedidoForm)
        self.assertEqual(form.instance, self.pedido)
        self.assertTrue(response.context['es_edicion'])
        self.assertEqual(response.context['pedido_id'], self.pedido.id)
        sel = json.loads(response.context['productos_seleccionados'])
        self.assertEqual(sel[str(self.prod1.id)], 3)
        cats = response.context['categorias']
        self.assertIn('Cervezas', cats)
        self.assertIn(self.prod1, cats['Cervezas'])
        self.assertIn(self.prod2, cats['Tapas o ½ Ración'])

    def test_post_adds_and_updates_line_items_and_redirects(self):
        """POST válido añade prod2 y actualiza cantidad de prod1, redirige a lista_pedidos."""
        self.client.login(username='tester', password='test1234')

        post_data = {
            'mesa': self.pedido.mesa,
            'numero_clientes': self.pedido.numero_clientes,
            'productos': [str(self.prod1.id), str(self.prod2.id)],
            'cantidades': json.dumps({
                str(self.prod1.id): 2,
                str(self.prod2.id): 5
            })
        }

        response = self.client.post(self.url(self.pedido.id), post_data)
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        pp1 = PedidoProducto.objects.get(pedido=self.pedido, producto=self.prod1)
        self.assertEqual(pp1.cantidad, 5)
        pp2 = PedidoProducto.objects.get(pedido=self.pedido, producto=self.prod2)
        self.assertEqual(pp2.cantidad, 5)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.camarero, self.user)

    def test_post_invalid_form_shows_errors_and_no_change(self):
        """POST inválido (sin productos) vuelve a mostrar form con errores; no elimina líneas."""
        self.client.login(username='tester', password='test1234')

        # Campos obligatorios, pero 'productos' vacío → form inválido
        post_data = {
            'mesa': self.pedido.mesa,
            'numero_clientes': self.pedido.numero_clientes,
            'productos': [],
            'cantidades': '{}'
        }
        response = self.client.post(self.url(self.pedido.id), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crear_pedido.html')
        form = response.context['form']
        self.assertTrue(form.errors)
        pp1 = PedidoProducto.objects.get(pedido=self.pedido, producto=self.prod1)
        self.assertEqual(pp1.cantidad, 3)

class EliminarProductoPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        # Un pedido y dos productos
        self.pedido = Pedido.objects.create(
            mesa='1', numero_clientes=2, camarero=self.user, pagado=False
        )
        self.prod1 = Producto.objects.create(nombre='P1', categoria='A', precio='1.00')
        self.prod2 = Producto.objects.create(nombre='P2', categoria='B', precio='2.00')

    def url(self, pedido_id, producto_id):
        return reverse('eliminar_producto_pedido', args=[pedido_id, producto_id])

    def test_redirect_if_not_logged_in(self):
        """Acceso anónimo redirige al login con next."""
        url = self.url(self.pedido.id, self.prod1.id)
        response = self.client.get(url)
        expected = f"{self.login_url}?next={url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_nonexistent_pedido_returns_404(self):
        """Si el pedido no existe, devuelve 404."""
        self.client.login(username='tester', password='test1234')
        url = self.url(9999, self.prod1.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_producto_returns_404(self):
        """Si el producto no existe, devuelve 404."""
        self.client.login(username='tester', password='test1234')
        url = self.url(self.pedido.id, 9999)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_decrement_quantity_when_more_than_one(self):
        """Si hay cantidad >1, la vista la decrementa en uno."""
        self.client.login(username='tester', password='test1234')
        # Crear línea con cantidad 3
        pp = PedidoProducto.objects.create(pedido=self.pedido, producto=self.prod1, cantidad=3)
        url = self.url(self.pedido.id, self.prod1.id)
        response = self.client.get(url)
        # Redirige a detalles_pedido sin seguir
        expected_redirect = reverse('detalles_pedido', args=[self.pedido.id])
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)
        # Refrescamos y comprobamos decremento
        pp.refresh_from_db()
        self.assertEqual(pp.cantidad, 2)

    def test_delete_line_when_quantity_is_one(self):
        """Si la cantidad es 1, borrar la línea."""
        self.client.login(username='tester', password='test1234')
        pp = PedidoProducto.objects.create(pedido=self.pedido, producto=self.prod2, cantidad=1)
        url = self.url(self.pedido.id, self.prod2.id)
        response = self.client.get(url)
        expected_redirect = reverse('detalles_pedido', args=[self.pedido.id])
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)
        # La línea debe haber sido eliminada
        self.assertFalse(PedidoProducto.objects.filter(id=pp.id).exists())

    def test_no_line_silently_redirects(self):
        """Si no existe línea para ese pedido y producto, simplemente redirige."""
        self.client.login(username='tester', password='test1234')
        # No creamos ningún PedidoProducto
        url = self.url(self.pedido.id, self.prod1.id)
        response = self.client.get(url)
        expected_redirect = reverse('detalles_pedido', args=[self.pedido.id])
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)
        # Verificamos que efectivamente no hay líneas
        self.assertFalse(PedidoProducto.objects.filter(pedido=self.pedido, producto=self.prod1).exists())

class CrearPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.login_url = reverse('login')
        self.url = reverse('crear_pedido')
        # Productos para categorías, incluyendo cafés para la lógica de kilos_disponibles
        self.prod_cafe = Producto.objects.create(
            nombre='Café Solo', categoria='Cafés', precio=Decimal('1.00'),
            kilos_disponibles=Decimal('0.016')
        )
        self.prod_normal = Producto.objects.create(
            nombre='Tapas1', categoria='Tapas', precio=Decimal('2.00')
        )

    def test_redirect_if_not_logged_in(self):
        """GET /crear_pedido/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_renders_form_and_categories(self):
        """GET autenticado muestra crear_pedido.html con form y categorías correctas."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crear_pedido.html')
        # Formulario en contexto
        form = response.context['form']
        self.assertIsInstance(form, PedidoForm)
        # Categorías: debe incluir ambas categorías
        cats = response.context['categorias']
        self.assertIn('Cafés', cats)
        self.assertIn('Tapas', cats)
        # Lógica de cafés: kilos_disponibles 0.016 / 0.008 = 2 tazas
        cafe_obj = [p for p in cats['Cafés'] if p.id == self.prod_cafe.id][0]
        self.assertEqual(cafe_obj.cantidad, 2)

    def test_post_valid_creates_pedido_and_line_items_and_redirects(self):
        """POST válido crea Pedido, sus líneas con cantidad y nota, y redirige."""
        self.client.login(username='tester', password='test1234')
        cantidades = {
            str(self.prod_cafe.id): 3,
            str(self.prod_normal.id): 5
        }
        data = {
            'mesa': 'M1',
            'numero_clientes': 4,
            'productos': [str(self.prod_cafe.id), str(self.prod_normal.id)],
            'cantidades': json.dumps(cantidades),
            f'nota_{self.prod_cafe.id}': 'Con azúcar',
            f'nota_{self.prod_normal.id}': ''
        }
        response = self.client.post(self.url, data)
        # Debe redirigir a lista_pedidos_confirmado con el nuevo pedido.id
        pedido = Pedido.objects.first()
        expected_url = reverse('lista_pedidos_confirmado', args=[pedido.id])
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        # Pedido creado correctamente
        self.assertEqual(pedido.mesa, 'M1')
        self.assertEqual(pedido.numero_clientes, 4)
        self.assertEqual(pedido.camarero, self.user)
        # Líneas de pedido
        pp_cafe = PedidoProducto.objects.get(pedido=pedido, producto=self.prod_cafe)
        self.assertEqual(pp_cafe.cantidad, 3)
        self.assertEqual(pp_cafe.nota, 'Con azúcar')
        pp_norm = PedidoProducto.objects.get(pedido=pedido, producto=self.prod_normal)
        self.assertEqual(pp_norm.cantidad, 5)
        self.assertIsNone(pp_norm.nota)

    def test_post_invalid_shows_errors_and_does_not_create(self):
        """POST inválido (sin campos obligatorios) vuelve a renderizar y no crea nada."""
        self.client.login(username='tester', password='test1234')
        data = {
            # 'mesa' y 'numero_clientes' faltantes → form inválido
            'productos': [str(self.prod_cafe.id)],
            'cantidades': '{}'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'crear_pedido.html')
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertFalse(Pedido.objects.exists())

class StockViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('stock')
        self.user = User.objects.create_user(username='user', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')
        Producto.objects.create(nombre='Pan Blanco', categoria='Pan', precio=1)
        self.p1 = Producto.objects.create(nombre='Cerveza Con', categoria='Cervezas', precio=2, es_barril=True)
        self.p2 = Producto.objects.create(nombre='Tubo Sin', categoria='Cervezas', precio=2, es_barril=True)
        self.p3 = Producto.objects.create(nombre='Filete', categoria='Carnes Ibéricas', precio=5, kilos_disponibles=None)
        self.p4 = Producto.objects.create(nombre='Serranito', categoria='Bocadillos', precio=3, kilos_disponibles=None)
        self.p5 = Producto.objects.create(nombre='Montado de Lomo', categoria='Bocadillos', precio=3, kilos_disponibles=None)
        self.p6 = Producto.objects.create(nombre='Pollo Kentaky', categoria='Entrantes', precio=4, kilos_disponibles=None)
        self.p7 = Producto.objects.create(nombre='Ensalada Atún', categoria='Entrantes', precio=3, kilos_disponibles=None)
        self.p8 = Producto.objects.create(nombre='Ensalada Rulo Cabra', categoria='Entrantes', precio=3, kilos_disponibles=None)
        self.p9 = Producto.objects.create(nombre='Café Solo', categoria='Cafés', precio=1, kilos_disponibles=None)

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{self.login_url}?next={self.url}', fetch_redirect_response=False)

    def test_permission_denied_for_non_admin(self):
        """Usuario autenticado pero no admin es redirigido al login con next."""
        self.client.login(username='user', password='pass')
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_get_shows_categories_and_excludes_pan(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'stock.html')
        por_cat = response.context['productos_por_categoria']
        # 'Pan' excluded
        self.assertNotIn('Pan', por_cat)
        for c in ['Cervezas','Carnes Ibéricas','Bocadillos','Entrantes','Cafés']:
            self.assertIn(c, por_cat)
        self.assertCountEqual(response.context['categorias'], list(por_cat.keys()))
        prod_ids = {p.id for p in por_cat['Cervezas']} \
                 | {p.id for p in por_cat['Carnes Ibéricas']} \
                 | {p.id for p in por_cat['Bocadillos']} \
                 | {p.id for p in por_cat['Entrantes']} \
                 | {p.id for p in por_cat['Cafés']}
        filt_ids = {p.id for p in response.context['productos_filtrados']}
        self.assertEqual(prod_ids, filt_ids)

    def test_get_with_category_filter(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url, {'categoria': 'Bocadillos'})
        filt = response.context['productos_filtrados']
        self.assertCountEqual([p.id for p in filt], [self.p4.id, self.p5.id])
        self.assertEqual(response.context['categoria_seleccionada'], 'Bocadillos')

    def test_post_barril_group1_updates_all(self):
        self.client.login(username='admin', password='pass')
        # Group1: ['Cerveza Con', 'Tubo Con', 'Cortada', 'Cañón']
        p_extra = Producto.objects.create(nombre='Cañón', categoria='Cervezas', precio=2, es_barril=True)
        data = {'producto_id': str(self.p1.id), 'categoria_seleccionada': 'Cervezas', 'litros_disponibles': '5.5'}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Cervezas', fetch_redirect_response=False)
        for p in [self.p1, p_extra]:
            p.refresh_from_db()
            self.assertEqual(p.litros_disponibles, 5.5)

    def test_post_carnes_updates_kilos(self):
        """POST a Carnes Ibéricas actualiza kilos_disponibles como Decimal."""
        self.client.login(username='admin', password='pass')
        data = {
            'producto_id': str(self.p3.id),
            'categoria_seleccionada': 'Carnes Ibéricas',
            'kilos_disponibles': '3.2'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Carnes Ibéricas', fetch_redirect_response=False)
        self.p3.refresh_from_db()
        self.assertEqual(self.p3.kilos_disponibles, Decimal('3.2'))

    def test_post_bocadillos_group_updates(self):
        """POST a Bocadillos actualiza kilos_disponibles del grupo como Decimal."""
        self.client.login(username='admin', password='pass')
        data = {
            'producto_id': str(self.p4.id),
            'categoria_seleccionada': 'Bocadillos',
            'kilos_disponibles': '7.1'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Bocadillos', fetch_redirect_response=False)
        for p in [self.p4, self.p5]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('7.1'))

    def test_post_entrantes_individual(self):
        """POST a Entrantes individual actualiza kilos_disponibles como Decimal."""
        self.client.login(username='admin', password='pass')
        data = {
            'producto_id': str(self.p6.id),
            'categoria_seleccionada': 'Entrantes',
            'kilos_disponibles': '4.4'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Entrantes', fetch_redirect_response=False)
        self.p6.refresh_from_db()
        self.assertEqual(self.p6.kilos_disponibles, Decimal('4.4'))

    def test_post_ensaladas_group_updates(self):
        """POST a Entrantes (Ensaladas) actualiza grupo como Decimal."""
        self.client.login(username='admin', password='pass')
        data = {
            'producto_id': str(self.p7.id),
            'categoria_seleccionada': 'Entrantes',
            'kilos_disponibles': '2.2'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Entrantes', fetch_redirect_response=False)
        for p in [self.p7, self.p8]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('2.2'))

    def test_post_cafes_group_updates(self):
        """POST a Cafés actualiza kilos_disponibles del subgrupo como Decimal."""
        self.client.login(username='admin', password='pass')
        data = {
            'producto_id': str(self.p9.id),
            'categoria_seleccionada': 'Cafés',
            'kilos_disponibles': '1.8'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, '/stock?categoria=Cafés', fetch_redirect_response=False)
        afectados = Producto.objects.filter(
            categoria='Cafés',
            nombre__in=["Café Leche", "Café Solo", "Café Cortado"]
        )
        for p in afectados:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('1.8'))

class PagarPedidoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')
    def create_pedido_with_stock(self, **products):
        """
        Helper: create a new unpaid Pedido with given products.
        products: dict of product kwargs to initial stock fields.
        Returns (pedido, {prod_name: Producto})
        """
        pedido = Pedido.objects.create(
            mesa='1', numero_clientes=1, camarero=self.user, pagado=False
        )
        created = {}
        for name, attrs in products.items():
            prod = Producto.objects.create(nombre=name, **attrs)
            PedidoProducto.objects.create(pedido=pedido, producto=prod, cantidad=attrs.get('cantidad',1))
            created[name] = prod
        return pedido, created

    def test_redirect_if_not_logged_in(self):
        pedido = Pedido.objects.create(mesa='1', numero_clientes=1,
                                       camarero=self.user, pagado=False)
        url = reverse('pagar_pedido', args=[pedido.id])
        response = self.client.get(url)
        self.assertRedirects(response, f'{self.login_url}?next={url}', fetch_redirect_response=False)

    def test_marks_as_paid_and_sets_fecha_cierre(self):
        pedido = Pedido.objects.create(mesa='1', numero_clientes=1,
                                       camarero=self.user, pagado=False)
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        before = timezone.now()
        response = self.client.get(url)
        self.assertRedirects(response, reverse('lista_pedidos'), fetch_redirect_response=False)
        pedido.refresh_from_db()
        self.assertTrue(pedido.pagado)
        self.assertTrue(pedido.fecha_cierre >= before)

    def test_conversion_litros_group_con(self):
        """Los barriles de grupo_con acumulan descuento por cada línea."""
        pedido, prods = self.create_pedido_with_stock(
            **{
                'Cerveza Con': {'categoria':'Cervezas','precio':1,'es_barril':True,'litros_disponibles':Decimal('10'),'cantidad':2},
                'Tubo Con':    {'categoria':'Cervezas','precio':1,'es_barril':True,'litros_disponibles':Decimal('8'),'cantidad':1},
            }
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ['Cerveza Con','Tubo Con']:
            prod = Producto.objects.get(nombre=name)
            self.assertEqual(prod.litros_disponibles, Decimal('9.35'))

    def test_conversion_litros_group_sin(self):
        """Los barriles de grupo_sin acumulan descuento por cada línea."""
        pedido, prods = self.create_pedido_with_stock(
            **{
                'Cerveza Sin': {'categoria':'Cervezas','precio':1,'es_barril':True,'litros_disponibles':Decimal('5'),'cantidad':3},
                'Tubo Sin':    {'categoria':'Cervezas','precio':1,'es_barril':True,'litros_disponibles':Decimal('2'),'cantidad':1},
            }
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ['Cerveza Sin','Tubo Sin']:
            prod = Producto.objects.get(nombre=name)
            self.assertEqual(prod.litros_disponibles, Decimal('4.15'))

    def test_wine_discount(self):
        pedido, prods = self.create_pedido_with_stock(
            **{
                'Ramón Bilbao Crianza': {'categoria':'Vinos','precio':1,'es_barril':False,'litros_disponibles':Decimal('1.0'),'cantidad':2},
            }
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Ramón Bilbao Crianza')
        self.assertEqual(prod.litros_disponibles, Decimal('0.7'))

    def test_bottle_discount(self):
        """POST con venta de botella resta toda la cantidad vendida."""
        pedido, prods = self.create_pedido_with_stock(
            **{'Botella X': {
                'categoria':'Bebidas',
                'precio':1,
                'es_barril':False,
                'cantidad':5
            }}
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Botella X')
        self.assertEqual(prod.cantidad, 0)

    def test_entrantes_kilos(self):
        pedido, prods = self.create_pedido_with_stock(
            **{'Pollo Kentaky': {'categoria':'Entrantes','precio':1,'es_barril':False,'kilos_disponibles':Decimal('2.0'),'cantidad':4}}
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Pollo Kentaky')
        self.assertEqual(prod.kilos_disponibles, Decimal('0.8'))

    def test_ensaladas_group(self):
        pedido, prods = self.create_pedido_with_stock(
            **{
                'Ensalada Atún': {'categoria':'Entrantes','precio':1,'es_barril':False,'kilos_disponibles':Decimal('1.0'),'cantidad':1},
            }
        )
        Producto.objects.create(
            nombre='Ensalada Rulo Cabra', categoria='Entrantes',
            precio=1, es_barril=False, kilos_disponibles=Decimal('1.0')
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ["Ensalada Atún","Ensalada Rulo Cabra"]:
            self.assertEqual(
                Producto.objects.get(nombre=name).kilos_disponibles,
                Decimal('0.7')
            )

    def test_croquetas_discount(self):
        pedido, prods = self.create_pedido_with_stock(
            **{'Croquetas Caseras': {'categoria':'Entrantes','precio':1,'es_barril':False,'cantidad':2}}
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Croquetas Caseras')
        self.assertEqual(prod.cantidad, max(0, 0 - 20))

    def test_carnes_pescados_discount(self):
        pedido, prods = self.create_pedido_with_stock(
            **{'Filete': {'categoria':'Carnes Ibéricas','precio':1,'es_barril':False,'kilos_disponibles':Decimal('1.0'),'cantidad':1}}
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Filete')
        self.assertEqual(prod.kilos_disponibles, Decimal('0.7'))

    def test_bocadillos_descuento_group(self):
        pedido, prods = self.create_pedido_with_stock(
            **{'Serranito': {'categoria':'Bocadillos','precio':1,'es_barril':False,'kilos_disponibles':Decimal('1.0'),'cantidad':3}}
        )
        Producto.objects.create(
            nombre='Montado de Lomo', categoria='Bocadillos',
            precio=1, es_barril=False, kilos_disponibles=Decimal('1.0')
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ["Serranito","Montado de Lomo"]:
            self.assertEqual(
                Producto.objects.get(nombre=name).kilos_disponibles,
                Decimal('0.4')
            )

    def test_cafe_group_discount(self):
        """Los cafés restan 0.008 kg por unidad y acumulan en el grupo."""
        pedido = Pedido.objects.create(mesa='1', numero_clientes=1, camarero=self.user, pagado=False)
        for name in ["Café Leche","Café Solo","Café Cortado"]:
            p = Producto.objects.create(
                nombre=name, categoria='Cafés', precio=1,
                es_barril=False, kilos_disponibles=Decimal('1.0')
            )
            PedidoProducto.objects.create(pedido=pedido, producto=p, cantidad=2)
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ["Café Leche","Café Solo","Café Cortado"]:
            self.assertEqual(
                Producto.objects.get(nombre=name).kilos_disponibles,
                Decimal('0.94')
            )

    def test_descafeinados_group_discount(self):
        """Los descafeinados restan 0.008 kg por unidad y acumulan en el grupo."""
        pedido = Pedido.objects.create(mesa='1', numero_clientes=1, camarero=self.user, pagado=False)
        for name in ["Desca Leche","Desca Cortado","Desca Solo"]:
            p = Producto.objects.create(
                nombre=name, categoria='Cafés', precio=1,
                es_barril=False, kilos_disponibles=Decimal('1.0')
            )
            PedidoProducto.objects.create(pedido=pedido, producto=p, cantidad=1)
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        for name in ["Desca Leche","Desca Cortado","Desca Solo"]:
            self.assertEqual(
                Producto.objects.get(nombre=name).kilos_disponibles,
                Decimal('0.97')
            )

    def test_other_product_unit_discount(self):
        """Productos no barril restan 1 unidad por cada unidad vendida."""
        pedido, prods = self.create_pedido_with_stock(
            **{'Snack': {
                'categoria':'Otros','precio':1,
                'es_barril':False,'cantidad':5
            }}
        )
        url = reverse('pagar_pedido', args=[pedido.id])
        self.client.login(username='tester', password='test1234')
        self.client.get(url)
        prod = Producto.objects.get(nombre='Snack')
        self.assertEqual(prod.cantidad, 0)

class RegistrarEntradaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.url = reverse('registrar_entrada')
        self.redirect_url = reverse('control_horarios')

    def test_redirects_to_control_horarios_and_shows_message(self):
        """Registrar entrada debe redirigir a control_horarios y emitir mensaje de éxito."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertRedirects(response, self.redirect_url, fetch_redirect_response=False)
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Hora de entrada registrada. Cronómetro iniciado." in m.message for m in msgs))

    def test_creates_new_and_closes_old(self):
        """Si existe un registro activo, lo cierra y crea uno nuevo activo."""
        self.client.login(username='tester', password='test1234')
        # Creamos un registro activo previo
        old = RegistroHorario.objects.create(camarero=self.user, activo=True)
        # hora_salida inicialmente None
        self.assertIsNone(old.hora_salida)
        # Llamamos a la vista
        self.client.get(self.url)
        # Refrescamos old desde BD
        old.refresh_from_db()
        self.assertFalse(old.activo)
        self.assertIsNotNone(old.hora_salida)
        # Debe existir un nuevo registro activo sin hora_salida
        new = RegistroHorario.objects.exclude(id=old.id).get(camarero=self.user)
        self.assertTrue(new.activo)
        self.assertIsNone(new.hora_salida)

    def test_closes_all_existing_actives_before_creating_new(self):
        """Si hay múltiples registros activos, todos se cierran antes de crear el nuevo."""
        self.client.login(username='tester', password='test1234')
        regs = [RegistroHorario.objects.create(camarero=self.user, activo=True) for _ in range(2)]
        self.client.get(self.url)
        # Todos los antiguos deben estar cerrados
        for r in regs:
            r.refresh_from_db()
            self.assertFalse(r.activo)
            self.assertIsNotNone(r.hora_salida)
        # Y debe haber exactamente un único registro activo
        active_regs = RegistroHorario.objects.filter(camarero=self.user, activo=True)
        self.assertEqual(active_regs.count(), 1)
        new = active_regs.first()
        self.assertIsNone(new.hora_salida)

    def test_creates_entry_when_no_old_present(self):
        """Si no hay registros previos, simplemente crea uno nuevo activo."""
        self.client.login(username='tester', password='test1234')
        self.assertFalse(RegistroHorario.objects.filter(camarero=self.user).exists())
        self.client.get(self.url)
        reg = RegistroHorario.objects.get(camarero=self.user)
        self.assertTrue(reg.activo)
        self.assertIsNone(reg.hora_salida)

class RegistrarSalidaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.url = reverse('registrar_salida')
        self.redirect_url = reverse('control_horarios')

    def test_redirect_if_not_logged_in(self):
        """GET /registrar_salida/ sin login redirige al login con next."""
        response = self.client.get(self.url)
        login_url = reverse('login')
        expected = f"{login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_records_exit_and_shows_success_message(self):
        """Con registro activo, la vista cierra el turno, guarda hora_salida y muestra mensaje."""
        self.client.login(username='tester', password='test1234')
        # Crear un turno activo
        reg = RegistroHorario.objects.create(camarero=self.user, activo=True)
        response = self.client.get(self.url)
        # Debe redirigir a control_horarios
        self.assertRedirects(response, self.redirect_url, fetch_redirect_response=False)
        # Recargar y comprobar cambios
        reg.refresh_from_db()
        self.assertFalse(reg.activo)
        self.assertIsNotNone(reg.hora_salida)
        # Mensaje de éxito
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Hora de salida registrada. Cronómetro reiniciado." in m.message for m in msgs))

    def test_no_active_turn_shows_error_message(self):
        """Sin registro activo, no hay cambios y se muestra mensaje de error."""
        self.client.login(username='tester', password='test1234')
        # Aseguramos que no existe turno activo
        RegistroHorario.objects.create(camarero=self.user, activo=False, hora_salida=timezone.now())
        response = self.client.get(self.url)
        self.assertRedirects(response, self.redirect_url, fetch_redirect_response=False)
        # No se crea ningún nuevo registro y los existentes no cambian
        regs = RegistroHorario.objects.filter(camarero=self.user)
        self.assertEqual(regs.count(), 1)
        self.assertFalse(regs.first().activo)
        # Mensaje de error
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("No tienes un turno activo." in m.message for m in msgs))

    def test_second_call_after_exit_also_errors(self):
        """Tras un primer exit válido, una segunda llamada produce mensaje de error."""
        self.client.login(username='tester', password='test1234')
        reg = RegistroHorario.objects.create(camarero=self.user, activo=True)
        # Primera llamada cierra el turno
        self.client.get(self.url)
        # Segunda llamada
        response2 = self.client.get(self.url)
        self.assertRedirects(response2, self.redirect_url, fetch_redirect_response=False)
        # Mensaje de error en la segunda llamada
        msgs = list(get_messages(response2.wsgi_request))
        self.assertTrue(any("No tienes un turno activo." in m.message for m in msgs))

class ExportarHorariosPDFViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('exportar_horarios_pdf')
        self.user = User.objects.create_user(username='u1', password='pass')
        self.other = User.objects.create_user(username='u2', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')

        now = timezone.now()
        rh1 = RegistroHorario.objects.create(camarero=self.user, activo=False)
        rh1.hora_entrada = now - timedelta(hours=2)
        rh1.hora_salida = now - timedelta(hours=1)
        rh1.save()
        rh2 = RegistroHorario.objects.create(camarero=self.other, activo=False)
        rh2.hora_entrada = now - timedelta(hours=3)
        rh2.hora_salida = now - timedelta(hours=2)
        rh2.save()

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_pdf_response_for_normal_user(self):
        """Logged-in non-superuser gets a PDF with only their own registros."""
        self.client.login(username='u1', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 100)

    def test_pdf_response_for_superuser_includes_all(self):
        """Superuser sees a PDF containing registros for all users."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.client.logout()
        self.client.login(username='u1', password='pass')
        resp_user = self.client.get(self.url)
        self.assertGreater(len(response.content), len(resp_user.content))

class ControlHorariosViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('control_horarios')
        self.user = User.objects.create_user(username='u1', password='pass')
        self.user2 = User.objects.create_user(username='u2', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')
        now = timezone.now()
        self.r1 = RegistroHorario.objects.create(camarero=self.user, activo=False,
                                                 hora_entrada=now - timedelta(days=5))
        self.r2 = RegistroHorario.objects.create(camarero=self.user, activo=False,
                                                 hora_entrada=now - timedelta(days=2))
        self.r3 = RegistroHorario.objects.create(camarero=self.user2, activo=False,
                                                 hora_entrada=now - timedelta(days=3))
        self.r_active = RegistroHorario.objects.create(camarero=self.user, activo=True,
                                                       hora_entrada=now - timedelta(hours=1))

    def test_redirect_if_not_logged_in(self):
        """GET /control_horarios/ sin login redirige a login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_non_superuser_sees_only_their_registros(self):
        """Usuario normal ve sólo sus propios registros, sin filtros de camareros."""
        self.client.login(username='u1', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        registros = list(response.context['registros'])
        self.assertEqual(registros, [self.r_active, self.r2, self.r1])
        self.assertIsNone(response.context['selected_camarero'])
        self.assertIsNone(response.context['camareros'])
        self.assertEqual(response.context['registro_activo'], self.r_active)

    def test_non_superuser_date_filters(self):
        """Usuario normal puede filtrar por fecha_inicio y fecha_fin."""
        self.client.login(username='u1', password='pass')
        inicio = (self.r1.hora_entrada.date()).isoformat()
        fin = (self.r2.hora_entrada.date()).isoformat()
        response = self.client.get(self.url, {'fecha_inicio': inicio, 'fecha_fin': fin})
        registros = list(response.context['registros'])
        self.assertEqual(registros, [self.r2, self.r1])


    def test_superuser_sees_all_and_camareros_list(self):
        """Superuser ve todos los registros y una lista de camareros distintos."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url)
        registros = list(response.context['registros'])
        expected_order = sorted(
            [self.r1, self.r2, self.r3, self.r_active],
            key=lambda r: r.hora_entrada,
            reverse=True
        )
        self.assertEqual(registros, expected_order)
        camareros = response.context['camareros']
        self.assertCountEqual(list(camareros), [self.user, self.user2])
        self.assertEqual(response.context['selected_camarero'], '')

    def test_superuser_filter_by_camarero_and_dates(self):
        """Superuser puede filtrar por camarero, fecha_inicio y fecha_fin."""
        self.client.login(username='admin', password='pass')
        inicio = (self.r3.hora_entrada.date()).isoformat()
        response = self.client.get(self.url, {
            'camarero': str(self.user2.id),
            'fecha_inicio': inicio
        })
        registros = list(response.context['registros'])
        self.assertEqual(registros, [self.r3])
        self.assertEqual(response.context['selected_camarero'], str(self.user2.id))

    def test_superuser_no_active_for_self(self):
        """Superuser sin registro activo propio obtiene registro_activo None."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(self.url)
        self.assertIsNone(response.context['registro_activo'])

class ActualizarNotaProductoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.pedido = Pedido.objects.create(mesa='1', numero_clientes=2, camarero=self.user, pagado=False)
        self.producto = Producto.objects.create(nombre='Prod', categoria='Cat', precio=1.00)
        self.pp = PedidoProducto.objects.create(pedido=self.pedido, producto=self.producto, cantidad=1, nota='Old note')
        self.url = reverse('actualizar_nota_producto', args=[self.pedido.id, self.pp.id])
        self.detail_url = reverse('detalles_pedido', args=[self.pedido.id])
        self.login_url = reverse('login')

    def test_redirect_if_not_logged_in(self):
        """Unlogged GET redirects to login."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_404_if_mismatched_ids(self):
        """Using wrong pedido_id or producto_pedido_id returns 404."""
        self.client.login(username='tester', password='test1234')
        bad_url1 = reverse('actualizar_nota_producto', args=[9999, self.pp.id])
        response1 = self.client.post(bad_url1, {'nota': 'X'})
        self.assertEqual(response1.status_code, 404)
        bad_url2 = reverse('actualizar_nota_producto', args=[self.pedido.id, 9999])
        response2 = self.client.post(bad_url2, {'nota': 'X'})
        self.assertEqual(response2.status_code, 404)
        other_pedido = Pedido.objects.create(mesa='2', numero_clientes=1, camarero=self.user, pagado=False)
        bad_url3 = reverse('actualizar_nota_producto', args=[other_pedido.id, self.pp.id])
        response3 = self.client.post(bad_url3, {'nota': 'X'})
        self.assertEqual(response3.status_code, 404)

    def test_get_does_not_change_and_redirects(self):
        """GET should not update the note but still redirect."""
        self.client.login(username='tester', password='test1234')
        original = self.pp.nota
        response = self.client.get(self.url)
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)
        self.pp.refresh_from_db()
        self.assertEqual(self.pp.nota, original)
        msgs = list(get_messages(response.wsgi_request))
        self.assertFalse(msgs)

    def test_post_updates_note_and_shows_message(self):
        """POST updates the nota field, shows success message, and redirects."""
        self.client.login(username='tester', password='test1234')
        response = self.client.post(self.url, {'nota': '  New note  '})
        self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)
        self.pp.refresh_from_db()
        self.assertEqual(self.pp.nota, 'New note')
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Nota actualizada correctamente." in m.message for m in msgs))

class GenerarTicketPDFViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.pedido = Pedido.objects.create(
            mesa='42', numero_clientes=2, camarero=self.user, pagado=False
        )
        self.food = Producto.objects.create(nombre='Tapa', categoria='Tapas', precio=1.00)
        self.drink = Producto.objects.create(nombre='Cerveza', categoria='Cervezas', precio=2.00)
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.food, cantidad=2)
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.drink, cantidad=1)

        self.url = reverse('generar_ticket_pdf', args=[self.pedido.id])

    def test_redirect_if_not_logged_in(self):
        """Unlogged GET redirects to login with next parameter."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_pdf_response_contains_pdf_signature_and_correct_filename(self):
        """Logged-in user receives a PDF starting with '%PDF' and correct filename."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        cd = response['Content-Disposition']
        self.assertIn('attachment;', cd)
        self.assertIn(f'filename="ticket_mesa_{self.pedido.mesa}.pdf"', cd)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_error_branch_when_pisa_fails(self):
        """If pisa.CreatePDF reports an error, the view returns the error message."""
        self.client.login(username='tester', password='test1234')
        with patch.object(pisa, 'CreatePDF', return_value=type('r', (), {'err': True})()):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '❌ Error al generar el ticket de cocina')

class GenerarTicketClienteViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.pedido = Pedido.objects.create(
            mesa='7', numero_clientes=3, camarero=self.user, pagado=False
        )
        self.food = Producto.objects.create(nombre='Tapa', categoria='Tapas', precio=1.50)
        self.drink = Producto.objects.create(nombre='Refresco', categoria='Bebida/Refresco', precio=2.00)
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.food, cantidad=2)
        PedidoProducto.objects.create(pedido=self.pedido, producto=self.drink, cantidad=1)
        self.url = reverse('generar_ticket_cliente', args=[self.pedido.id])

    def test_redirect_if_not_logged_in(self):
        """Unlogged GET redirects al login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_pdf_response_contains_signature_and_filename(self):
        """Usuario autenticado recibe PDF con firma y nombre de archivo correcto."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        cd = response['Content-Disposition']
        self.assertIn('attachment;', cd)
        self.assertIn(f'filename="ticket_cliente_mesa_{self.pedido.mesa}.pdf"', cd)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 100)

    def test_error_branch_when_pisa_fails(self):
        """Si pisa.CreatePDF indica error, se devuelve mensaje de error."""
        self.client.login(username='tester', password='test1234')
        with patch.object(pisa, 'CreatePDF', return_value=type('res', (), {'err': True})()):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "❌ Error al generar el ticket del cliente")

class PagarProductoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.pedido = Pedido.objects.create(
            mesa='1', numero_clientes=1, camarero=self.user, pagado=False
        )

    def _make_pp(self, prod_kwargs, cantidad):
        prod_kwargs.setdefault('cantidad', 0)
        prod = Producto.objects.create(**prod_kwargs)
        pp = PedidoProducto.objects.create(pedido=self.pedido, producto=prod, cantidad=cantidad)
        return prod, pp

    def test_redirect_if_not_logged_in(self):
        prod, pp = self._make_pp({
            'nombre': 'Snack', 'categoria':'Otros','precio':1,'es_barril':False
        }, cantidad=1)
        url = reverse('pagar_producto', args=[self.pedido.id, pp.id])
        response = self.client.get(url)
        self.assertRedirects(response, f'{self.login_url}?next={url}', fetch_redirect_response=False)

    def test_404_for_invalid_ids(self):
        self.client.login(username='tester', password='test1234')
        self.assertEqual(self.client.get(reverse('pagar_producto', args=[9999, 1])).status_code, 404)
        self.assertEqual(self.client.get(reverse('pagar_producto', args=[self.pedido.id, 9999])).status_code, 404)

    def test_decrement_quantity_and_create_producto_pagado(self):
        prod, pp = self._make_pp({
            'nombre':'Snack','categoria':'Otros','precio':Decimal('2.00'),'es_barril':False
        }, cantidad=3)
        self.client.login(username='tester', password='test1234')
        url = reverse('pagar_producto', args=[self.pedido.id, pp.id])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('detalles_pedido', args=[self.pedido.id]), fetch_redirect_response=False)
        pp.refresh_from_db()
        self.assertEqual(pp.cantidad, 2)
        pago = ProductoPagado.objects.get(pedido=self.pedido, producto=prod)
        self.assertEqual(pago.cantidad, 1)
        self.assertEqual(pago.precio_unitario, prod.precio)

    def test_delete_line_when_quantity_one(self):
        prod, pp = self._make_pp({
            'nombre':'Snack','categoria':'Otros','precio':1,'es_barril':False
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        self.assertFalse(PedidoProducto.objects.filter(id=pp.id).exists())
        self.assertTrue(ProductoPagado.objects.filter(pedido=self.pedido, producto=prod).exists())

    def test_conversion_litros_group_con(self):
        p1, pp1 = self._make_pp({
            'nombre':'Cerveza Con','categoria':'Cervezas','precio':1,
            'es_barril':True,'litros_disponibles':Decimal('5')
        }, cantidad=2)
        p2, pp2 = self._make_pp({
            'nombre':'Tubo Con','categoria':'Cervezas','precio':1,
            'es_barril':True,'litros_disponibles':Decimal('3')
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2]:
            p.refresh_from_db()
            self.assertEqual(p.litros_disponibles, Decimal('4.8'))

    def test_conversion_litros_group_sin(self):
        p1, pp1 = self._make_pp({
            'nombre':'Cerveza Sin','categoria':'Cervezas','precio':1,
            'es_barril':True,'litros_disponibles':Decimal('4')
        }, cantidad=3)
        p2, pp2 = self._make_pp({
            'nombre':'Tubo Sin','categoria':'Cervezas','precio':1,
            'es_barril':True,'litros_disponibles':Decimal('2')
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2]:
            p.refresh_from_db()
            self.assertEqual(p.litros_disponibles, Decimal('3.8'))

    def test_wine_discount(self):
        p, pp = self._make_pp({
            'nombre':'Ramón Bilbao Crianza','categoria':'Vinos','precio':1,
            'es_barril':False,'litros_disponibles':Decimal('1.0')
        }, cantidad=2)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        p.refresh_from_db()
        self.assertEqual(p.litros_disponibles, Decimal('0.85'))

    def test_bottle_discount(self):
        p, pp = self._make_pp({
            'nombre':'Botella Vino','categoria':'Bebidas','precio':1,
            'es_barril':False,'cantidad':5
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 4)

    def test_entrantes_kilos(self):
        p, pp = self._make_pp({
            'nombre':'Pollo Kentaky','categoria':'Entrantes','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('2.0')
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        p.refresh_from_db()
        self.assertEqual(p.kilos_disponibles, Decimal('1.7'))

    def test_ensaladas_group(self):
        p1, pp1 = self._make_pp({
            'nombre':'Ensalada Atún','categoria':'Entrantes','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        p2, pp2 = self._make_pp({
            'nombre':'Ensalada Rulo Cabra','categoria':'Entrantes','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('0.7'))

    def test_croquetas_discount(self):
        """POST paga croquetas descontando 10 unidades por ración."""
        p, pp = self._make_pp({
            'nombre':'Croquetas Caseras','categoria':'Entrantes','precio':1,
            'es_barril':False,'cantidad':20
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        p.refresh_from_db()
        self.assertEqual(p.cantidad, 10)

    def test_carnes_pescados_discount(self):
        p, pp = self._make_pp({
            'nombre':'Filete','categoria':'Carnes Ibéricas','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp.id]))
        p.refresh_from_db()
        self.assertEqual(p.kilos_disponibles, Decimal('0.7'))

    def test_bocadillos_group_discount(self):
        p1, pp1 = self._make_pp({
            'nombre':'Serranito','categoria':'Bocadillos','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        p2, pp2 = self._make_pp({
            'nombre':'Montado de Lomo','categoria':'Bocadillos','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=0)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('0.8'))

    def test_cafe_group_discount(self):
        p1, pp1 = self._make_pp({
            'nombre':'Café Solo','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        p2, _ = self._make_pp({
            'nombre':'Café Leche','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=0)
        p3, _ = self._make_pp({
            'nombre':'Café Cortado','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=0)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2, p3]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('0.99'))

    def test_descafeinados_group_discount(self):
        p1, pp1 = self._make_pp({
            'nombre':'Desca Solo','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=1)
        p2, _ = self._make_pp({
            'nombre':'Desca Leche','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=0)
        p3, _ = self._make_pp({
            'nombre':'Desca Cortado','categoria':'Cafés','precio':1,
            'es_barril':False,'kilos_disponibles':Decimal('1.0')
        }, cantidad=0)
        self.client.login(username='tester', password='test1234')
        self.client.get(reverse('pagar_producto', args=[self.pedido.id, pp1.id]))
        for p in [p1, p2, p3]:
            p.refresh_from_db()
            self.assertEqual(p.kilos_disponibles, Decimal('0.99'))

class PausarJornadaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('pausar_jornada')
        self.user = User.objects.create_user(username='tester', password='test1234')

    def test_redirect_if_not_logged_in(self):
        """GET /pausar_jornada/ sin login redirige a login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_pauses_active_shift_and_shows_success(self):
        """Con turno activo, pausar_jornada marca pausado=True y calcula tiempo_transcurrido."""
        self.client.login(username='tester', password='test1234')
        entrada = timezone.now() - timedelta(hours=2, minutes=30)
        reg = RegistroHorario.objects.create(
            camarero=self.user, activo=True, hora_entrada=entrada, pausado=False
        )
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('control_horarios'), fetch_redirect_response=False)
        reg.refresh_from_db()
        self.assertTrue(reg.pausado)
        self.assertTrue(isinstance(reg.tiempo_transcurrido, timedelta))
        self.assertAlmostEqual(reg.tiempo_transcurrido.total_seconds(), (timezone.now() - entrada).total_seconds(), delta=5)
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Jornada pausada correctamente." in m.message for m in msgs))

    def test_error_when_no_active_shift(self):
        """Si no hay turno activo, muestra mensaje de error y no crea/modifica registros."""
        self.client.login(username='tester', password='test1234')
        RegistroHorario.objects.create(camarero=self.user, activo=False, hora_entrada=timezone.now())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('control_horarios'), fetch_redirect_response=False)
        regs = RegistroHorario.objects.filter(camarero=self.user)
        self.assertTrue(all(not r.pausado for r in regs))
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("No tienes un turno activo para pausar." in m.message for m in msgs))   

class ReanudarJornadaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('reanudar_jornada')
        self.redirect_url = reverse('control_horarios')
        self.user = User.objects.create_user(username='tester', password='test1234')

    def test_redirect_if_not_logged_in(self):
        """GET /reanudar_jornada/ sin login redirige a login con next."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_restarts_paused_shift_and_shows_success(self):
        """Con turno activo y pausado, reanudar_jornada reactiva y ajusta hora_entrada."""
        self.client.login(username='tester', password='test1234')
        paused_duration = timedelta(hours=1, minutes=15)
        now = timezone.now()
        reg = RegistroHorario.objects.create(
            camarero=self.user,
            activo=True,
            pausado=True,
            hora_entrada=now - paused_duration - timedelta(minutes=5),
            tiempo_transcurrido=paused_duration
        )
        response = self.client.get(self.url)
        self.assertRedirects(response, self.redirect_url, fetch_redirect_response=False)
        reg.refresh_from_db()
        self.assertTrue(reg.activo)
        self.assertFalse(reg.pausado)
        self.assertEqual(reg.tiempo_transcurrido, timedelta(0))
        delta = timezone.now() - reg.hora_entrada
        self.assertAlmostEqual(delta.total_seconds(), paused_duration.total_seconds(), delta=5)
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Jornada reanudada correctamente." in m.message for m in msgs))

    def test_error_when_no_paused_shift(self):
        """Si no hay turno pausado, muestra mensaje de error y no altera registros."""
        self.client.login(username='tester', password='test1234')
        RegistroHorario.objects.create(
            camarero=self.user,
            activo=True,
            pausado=False,
            hora_entrada=timezone.now()
        )
        response = self.client.get(self.url)
        self.assertRedirects(response, self.redirect_url, fetch_redirect_response=False)
        regs = RegistroHorario.objects.filter(camarero=self.user)
        self.assertTrue(all(not r.pausado for r in regs))
        msgs = list(get_messages(response.wsgi_request))
        self.assertTrue(any("No tienes un turno pausado para reanudar." in m.message for m in msgs))

class ReporteViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.url = reverse('reporte')
        self.user = User.objects.create_user(username='tester', password='test1234')
        self.today = localtime(now()).date()
        self.date_str = self.today.isoformat()

        self.p1 = Producto.objects.create(nombre='Prod1', categoria='Cat1',
                                          precio=Decimal('10.00'))
        pedido1 = Pedido.objects.create(mesa='1', numero_clientes=1,
                                        camarero=self.user, pagado=True,
                                        fecha_cierre=now())
        PedidoProducto.objects.create(pedido=pedido1, producto=self.p1, cantidad=2)
        self.p2 = Producto.objects.create(nombre='Prod2', categoria='Cat2',
                                          precio=Decimal('5.00'))
        pedido2 = Pedido.objects.create(mesa='2', numero_clientes=2,
                                        camarero=self.user, pagado=True,
                                        fecha_cierre=now())
        PedidoProducto.objects.create(pedido=pedido2, producto=self.p2, cantidad=3)
        ProductoPagado.objects.create(
            producto=self.p1, cantidad=1,
            precio_unitario=self.p1.precio,
            fecha=self.today, pedido=pedido1, camarero=self.user
        )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_report_context_with_data(self):
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url, {'fecha': self.date_str})
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx['fecha'], self.today)

        rep = ctx['reporte_por_categoria']
        self.assertIn('Cat1', rep)
        item1 = rep['Cat1'][0]
        self.assertEqual(item1['nombre'], 'Prod1')
        self.assertEqual(item1['precio'], 10.0)
        self.assertEqual(item1['cantidad'], 3)
        self.assertEqual(item1['total'], Decimal('30.00'))
        self.assertIn('Cat2', rep)
        item2 = rep['Cat2'][0]
        self.assertEqual(item2['nombre'], 'Prod2')
        self.assertEqual(item2['precio'], 5.0)
        self.assertEqual(item2['cantidad'], 3)
        self.assertEqual(item2['total'], Decimal('15.00'))

        self.assertEqual(ctx['labels'], ['Cat1', 'Cat2'])
        self.assertEqual(ctx['values'], [3, 3])

        self.assertEqual(ctx['top_name'], 'Prod2')
        self.assertEqual(ctx['top_count'], 3)

        self.assertEqual(ctx['grand_total'], Decimal('45.00'))

        bar_labels = ctx['bar_labels']
        bar_values = ctx['bar_values']
        month_name = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                      'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][self.today.month-1]
        self.assertEqual(bar_labels, [month_name])
        self.assertEqual(bar_values, [35.0])

    def test_invalid_date_results_in_no_data(self):
        """Si la fecha es inválida, context['fecha'] es None y no hay datos."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url, {'fecha': 'invalid-date'})
        self.assertIsNone(response.context['fecha'])
        self.assertEqual(response.context['labels'], [])
        self.assertEqual(response.context['values'], [])

class ReportePDFViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('reporte_pdf')
        self.login_url = reverse('login')
        self.user = User.objects.create_user(username='tester', password='test1234')
        p1 = Pedido.objects.create(mesa='1', numero_clientes=1, camarero=self.user,
                                   pagado=True, fecha_cierre=now())
        prod1 = Producto.objects.create(nombre='A', categoria='X', precio=Decimal('2.00'))
        PedidoProducto.objects.create(pedido=p1, producto=prod1, cantidad=2)
        p2 = Pedido.objects.create(mesa='2', numero_clientes=2, camarero=self.user,
                                   pagado=True, fecha_cierre=now())
        prod2 = Producto.objects.create(nombre='B', categoria='Y', precio=Decimal('3.00'))
        PedidoProducto.objects.create(pedido=p2, producto=prod2, cantidad=1)

    def test_redirect_if_not_logged_in(self):
        """Anonymous users are redirected to login."""
        response = self.client.get(self.url)
        expected = f"{self.login_url}?next={self.url}"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_pdf_response_contains_pdf_signature_and_filename(self):
        """Authenticated user receives a valid PDF with correct headers."""
        self.client.login(username='tester', password='test1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        cd = response['Content-Disposition']
        self.assertIn('attachment;', cd)
        self.assertIn('filename="reporte_ventas.pdf"', cd)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreater(len(response.content), 100)

    def test_error_branch_generates_500_on_pisa_failure(self):
        """If the PDF generator errors, view returns HTTP 500 with error text."""
        self.client.login(username='tester', password='test1234')
        fake = type('res', (), {'err': True})
        with patch.object(pisa, 'CreatePDF', return_value=fake()):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content.decode(), 'Hubo un error generando el PDF')
