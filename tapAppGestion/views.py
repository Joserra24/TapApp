from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User
from .models import Pedido, Producto, PedidoProducto
import json

from django.http import HttpResponse
from .forms import ProductoForm, RegistroForm, EditProfileForm, PedidoForm, ActualizarStockForm


@login_required
def index(request):
    return render(request, 'index.html')

def agregar_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('menu')
    else:
        form = ProductoForm()
    return render(request, 'agregar_producto.html', {'form': form})

def salir(request):
    logout(request)
    return redirect('index')

def formulario_registro(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Tu cuenta ha sido creada. Ahora puedes iniciar sesión.")
            return redirect("profile")
    else:
        form = RegistroForm()
    
    return render(request, "register.html", {"form": form})

@login_required
def profile_view(request):
    return render(request, "profile.html", {"user": request.user})

def personal(request):
    usuarios = User.objects.all()
    return render(request, 'personal.html', {'usuarios': usuarios})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            password_changed = bool(form.cleaned_data.get("password1"))

            if password_changed:
                update_session_auth_hash(request, user)  # Mantiene la sesión activa
                messages.success(request, "Tu contraseña ha sido actualizada correctamente.")
            else:
                messages.success(request, "Tu perfil ha sido actualizado correctamente.")

            return redirect('index')
    else:
        form = EditProfileForm(instance=request.user)

    return render(request, 'edit_profile.html', {'form': form})

@login_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'El usuario ha sido eliminado.')
        return redirect('personal')
    return render(request, 'confirm_delete.html', {'user': user})

@login_required
def menu(request):
    productos = Producto.objects.all().order_by('categoria')
    categorias = {}
    for producto in productos:
        if producto.categoria not in categorias:
            categorias[producto.categoria] = []
        categorias[producto.categoria].append(producto)
    return render(request, 'menu.html', {'categorias': categorias})

@login_required
def producto_detalle(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    return render(request, 'producto_detalle.html', {'producto': producto})

@login_required
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'El producto ha sido actualizado.')
            return redirect('menu')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'editar_producto.html', {'form': form, 'producto': producto})

@login_required
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'El producto ha sido eliminado.')
        return redirect('menu')
    return render(request, 'confirmacion_eliminar_producto.html', {'producto': producto})

@login_required
def lista_pedidos(request):
    pedidos = Pedido.objects.all()
    pedidos_con_productos = []

    for pedido in pedidos:
        productos_pedido = PedidoProducto.objects.filter(pedido=pedido).select_related('producto')

         # Calcular el total del pedido sumando (precio * cantidad)
        total_pedido = sum(producto_pedido.producto.precio * producto_pedido.cantidad for producto_pedido in productos_pedido)

        pedidos_con_productos.append({
            'pedido': pedido,
            'productos': productos_pedido,
            'total_pedido': round(total_pedido, 2)  # Redondear a 2 decimales
        })

    return render(request, 'lista_pedidos.html', {'pedidos_con_productos': pedidos_con_productos})

@login_required
def detalles_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    productos_pedido = PedidoProducto.objects.filter(pedido=pedido).select_related('producto')

    total_pedido = sum(pp.producto.precio * pp.cantidad for pp in productos_pedido)

    return render(request, 'detalles_pedido.html', {
        'pedido': pedido,
        'productos_pedido': productos_pedido,
        'total_pedido': round(total_pedido, 2)
    })

@login_required
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    if request.method == 'POST':
        pedido.delete()
        return redirect('lista_pedidos')  # Redirige a la lista de pedidos después de eliminar

    return render(request, 'confirmacion_eliminar_pedido.html', {'pedido': pedido})

@login_required
def editar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.camarero = request.user  # Mantener el camarero original
            pedido.save()

            # Obtener los productos del formulario
            productos = request.POST.getlist('productos')
            cantidades = json.loads(request.POST.get('cantidades', '{}'))

            for producto_id in productos:
                producto = Producto.objects.get(id=producto_id)
                cantidad = int(cantidades.get(str(producto.id), 1))

                # Verificar si el producto ya está en el pedido
                pedido_producto, creado = PedidoProducto.objects.get_or_create(pedido=pedido, producto=producto)

                if creado:
                    # Si es un nuevo producto, lo añadimos con la cantidad seleccionada
                    pedido_producto.cantidad = cantidad
                else:
                    # Si ya estaba en el pedido, sumamos la nueva cantidad
                    pedido_producto.cantidad += cantidad

                pedido_producto.save()

            return redirect('lista_pedidos')

    else:
        form = PedidoForm(instance=pedido)

    # Obtener los productos actuales del pedido
    productos_pedido = PedidoProducto.objects.filter(pedido=pedido)
    productos_seleccionados = {str(pp.producto.id): pp.cantidad for pp in productos_pedido}

    # Organizar productos en categorías
    productos = Producto.objects.all().order_by('categoria')
    categorias = {}
    for producto in productos:
        if producto.categoria not in categorias:
            categorias[producto.categoria] = []
        categorias[producto.categoria].append(producto)

    return render(request, 'crear_pedido.html', {
        'form': form,
        'categorias': categorias,
        'productos_seleccionados': json.dumps(productos_seleccionados),
        'es_edicion': True,
        'pedido_id': pedido.id
    })

@login_required
def eliminar_producto_pedido(request, pedido_id, producto_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    producto = get_object_or_404(Producto, id=producto_id)

    # Buscar si el producto está en el pedido
    pedido_producto = PedidoProducto.objects.filter(pedido=pedido, producto=producto).first()

    if pedido_producto:
        # Si solo hay una unidad, eliminar el producto del pedido
        if pedido_producto.cantidad == 1:
            pedido_producto.delete()
        else:
            # Si hay más de una unidad, reducir la cantidad
            pedido_producto.cantidad -= 1
            pedido_producto.save()

    return redirect('detalles_pedido', pedido_id=pedido.id)


@login_required
def crear_pedido(request):
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.camarero = request.user  # Asignar el camarero automáticamente
            pedido.save()
            
            productos = request.POST.getlist('productos')
            cantidades = json.loads(request.POST.get('cantidades', '{}'))

            for producto_id in productos:
                producto = Producto.objects.get(id=producto_id)
                cantidad = cantidades.get(str(producto.id), 1)
                PedidoProducto.objects.create(pedido=pedido, producto=producto, cantidad=cantidad)

            return redirect('lista_pedidos')
    else:
        form = PedidoForm()
    
    productos = Producto.objects.all().order_by('categoria')
    categorias = {}
    for producto in productos:
        if producto.categoria not in categorias:
            categorias[producto.categoria] = []
        categorias[producto.categoria].append(producto)
    return render(request, 'crear_pedido.html', {'form': form, 'categorias': categorias})

@login_required
def stock(request):
    categoria_seleccionada = request.GET.get('categoria', None)
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        categoria_seleccionada = request.POST.get('categoria_seleccionada')
        producto = Producto.objects.get(id=producto_id)
        form = ActualizarStockForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect(f'/stock?categoria={categoria_seleccionada}')
    
    productos = Producto.objects.exclude(categoria__in=['Cafés', 'Pan']).order_by('categoria')
    productos_por_categoria = {}
    for producto in productos:
        if producto.categoria not in productos_por_categoria:
            productos_por_categoria[producto.categoria] = []
        productos_por_categoria[producto.categoria].append(producto)
    
    categorias = list(productos_por_categoria.keys())
    productos_filtrados = productos_por_categoria.get(categoria_seleccionada, []) if categoria_seleccionada else []
    
    return render(request, 'stock.html', {
        'productos_por_categoria': productos_por_categoria,
        'categorias': categorias,
        'productos_filtrados': productos_filtrados,
        'categoria_seleccionada': categoria_seleccionada
    })



