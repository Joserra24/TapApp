"""
URL configuration for TapApp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from tapAppGestion import views
from django.urls import reverse_lazy
from django.contrib.auth.views import LogoutView



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('crear_pedido/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    path('pedidos/<int:pedido_id>/', views.detalles_pedido, name='detalles_pedido'),
    path('eliminar_pedido/<int:pedido_id>/', views.eliminar_pedido, name='eliminar_pedido'),
    path('editar_pedido/<int:pedido_id>/', views.editar_pedido, name='editar_pedido'),
    path('eliminar_producto_pedido/<int:pedido_id>/<int:producto_id>/', views.eliminar_producto_pedido, name='eliminar_producto_pedido'),
    path('pagar_pedido/<int:pedido_id>/', views.pagar_pedido, name='pagar_pedido'),
    path('pedidos_cerrados/', views.lista_pedidos_cerrados, name='lista_pedidos_cerrados'),
    path('pedido_cerrado/<int:pedido_id>/', views.detalle_pedido_cerrado, name='detalle_pedido_cerrado'),
    path('pedido/<int:pedido_id>/producto/<int:producto_pedido_id>/nota/', views.actualizar_nota_producto, name='actualizar_nota_producto'),
    path('pedidos_cerrados/eliminar/<int:pedido_id>/', views.eliminar_pedido_cerrado, name='eliminar_pedido_cerrado'),
    path('pedidos/confirmado/<int:pedido_id>/', views.lista_pedidos, name='lista_pedidos_confirmado'),
    path('pagar_producto/<int:pedido_id>/<int:producto_pedido_id>/', views.pagar_producto, name='pagar_producto'),






    path("profile/", views.profile_view, name="profile"),
    path("register/", views.formulario_registro, name="register"),
    path("logout/", LogoutView.as_view(next_page=reverse_lazy("register")), name="logout"),
    path('agregar_producto/', views.agregar_producto, name='agregar_producto'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('salir/', views.salir, name='salir'),
    path('personal/', views.personal, name='personal'),
    path('editar_perfil/', views.edit_profile, name='editar_perfil'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('menu/', views.menu, name='menu'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),
    path('producto/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('producto/<int:producto_id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    path('stock/', views.stock, name='stock'),  # Nueva URL para la vista stock
    path('entrada/', views.registrar_entrada, name='registrar_entrada'),
    path('salida/', views.registrar_salida, name='registrar_salida'),
    path('control_horarios/', views.control_horarios, name='control_horarios'),
    path('control_horarios/exportar_pdf/', views.exportar_horarios_pdf, name='exportar_horarios_pdf'),
    path('pedidos/<int:pedido_id>/ticket_pdf/', views.generar_ticket_pdf, name='generar_ticket_pdf'),
    path('pedidos/<int:pedido_id>/ticket_cliente/', views.generar_ticket_cliente, name='generar_ticket_cliente'),




]

LOGIN_REDIRECT_URL = reverse_lazy("profile")

