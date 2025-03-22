from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User
from .models import Pedido, Producto, PedidoProducto
from django.utils.timezone import now, localtime, timedelta
from django.db.models import Sum, F
from decimal import Decimal


import json

from django.http import HttpResponse
from .forms import ProductoForm, RegistroForm, EditProfileForm, PedidoForm, ActualizarStockForm, RegistroForm
from .models import Producto, Pedido, RegistroHorario


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
    pedidos = Pedido.objects.filter(pagado=False).order_by('-fecha')  
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
def lista_pedidos_cerrados(request):
    filtro = request.GET.get('filtro', 'recientes')  # Obtener filtro de la URL (por defecto: "recientes")
    fecha_inicio = request.GET.get('fecha_inicio')  # Obtener fecha de inicio (si se usa filtro por fecha)
    fecha_fin = request.GET.get('fecha_fin')  # Obtener fecha de fin (si se usa filtro por fecha)

    pedidos = Pedido.objects.filter(pagado=True).order_by('-fecha_cierre')  # Pedidos pagados ordenados por fecha

    # Filtrado según el criterio seleccionado
    if filtro == "ultima_semana":
        pedidos = pedidos.filter(fecha_cierre__gte=now() - timedelta(days=7))
    elif filtro == "ultimo_mes":
        pedidos = pedidos.filter(fecha_cierre__gte=now() - timedelta(days=30))
    elif filtro == "ultimo_ano":
        pedidos = pedidos.filter(fecha_cierre__gte=now() - timedelta(days=365))
    elif filtro == "por_fecha" and fecha_inicio and fecha_fin:
        pedidos = pedidos.filter(fecha_cierre__date__range=[fecha_inicio, fecha_fin])
    elif filtro == "por_mes":
        mes = request.GET.get('mes')  # Mes en formato "YYYY-MM"
        if mes:
            pedidos = pedidos.filter(fecha_cierre__year=mes.split('-')[0], fecha_cierre__month=mes.split('-')[1])
    elif filtro == "por_dia":
        dia = request.GET.get('dia')  # Día en formato "YYYY-MM-DD"
        if dia:
            pedidos = pedidos.filter(fecha_cierre__date=dia)

    # Convertir fecha de cierre a hora de Madrid
    pedidos_con_precio = []
    for pedido in pedidos:
        total_pedido = pedido.pedidoproducto_set.aggregate(Sum('producto__precio'))['producto__precio__sum'] or 0
        pedido.fecha_cierre = localtime(pedido.fecha_cierre)
        pedidos_con_precio.append({'pedido': pedido, 'total_pedido': total_pedido, 'pedido.fecha_cierre': pedido.fecha_cierre})

    return render(request, 'lista_pedidos_cerrados.html', {
        'pedidos_con_precio': pedidos_con_precio,
        'filtro_actual': filtro
    })


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
def detalle_pedido_cerrado(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, pagado=True)
    productos_pedido = PedidoProducto.objects.filter(pedido=pedido)

    # Calcular el total correctamente: cantidad * precio
    total_pedido = productos_pedido.aggregate(total=Sum(F('cantidad') * F('producto__precio')))['total'] or 0
    total_pedido = round(Decimal(total_pedido), 2)  # Redondear a 2 decimales


    pedido.fecha_cierre = localtime(pedido.fecha_cierre)

    

    return render(request, 'detalles_pedido_cerrado.html', {
        'pedido': pedido,
        'productos_pedido': productos_pedido,
        'total_pedido': total_pedido,
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

    # Grupos de productos que comparten barril
    barril_grupo_1 = ["Cerveza Con", "Tubo Con", "Cortada", "Cañón"]
    barril_grupo_2 = ["Cerveza Sin", "Tubo Sin"]

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        categoria_seleccionada = request.POST.get('categoria_seleccionada')
        producto = Producto.objects.get(id=producto_id)

        if producto.es_barril:
            litros = request.POST.get('litros_disponibles', None)
            if litros is not None:
                try:
                    litros_float = float(litros)

                    if producto.nombre in barril_grupo_1:
                        relacionados = Producto.objects.filter(nombre__in=barril_grupo_1)
                    elif producto.nombre in barril_grupo_2:
                        relacionados = Producto.objects.filter(nombre__in=barril_grupo_2)
                    else:
                        relacionados = [producto]

                    for p in relacionados:
                        p.litros_disponibles = litros_float
                        p.save()

                except ValueError:
                    pass  # Valor no numérico, ignoramos
        else:
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


from decimal import Decimal

@login_required
def pagar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if not pedido.pagado:
        pedido.pagado = True
        pedido.fecha_cierre = now()
        pedido.save()

        productos_pedido = PedidoProducto.objects.filter(pedido=pedido)

        # Barril compartido: nombre => litros por unidad
        conversion_litros = {
            # Barril con alcohol
            "Cerveza Con": 0.2,
            "Tubo Con": 0.25,
            "Cortada": 0.275,
            "Cañón": 0.350,

            # Barril sin alcohol
            "Cerveza Sin": 0.2,
            "Tubo Sin": 0.25,

            # Radler - independiente
            "Radler": 0.2,
        }

        grupo_con = ["Cerveza Con", "Tubo Con", "Cortada", "Cañón"]
        grupo_sin = ["Cerveza Sin", "Tubo Sin"]

        for item in productos_pedido:
            producto = item.producto
            cantidad = item.cantidad

            if producto.nombre in conversion_litros:
                litros_por_unidad = conversion_litros[producto.nombre]
                litros_a_restar = Decimal(str(litros_por_unidad)) * cantidad

                if producto.nombre in grupo_con:
                    grupo = Producto.objects.filter(nombre__in=grupo_con)
                    barril_ref = grupo.filter(nombre="Cerveza Con").first()
                elif producto.nombre in grupo_sin:
                    grupo = Producto.objects.filter(nombre__in=grupo_sin)
                    barril_ref = grupo.filter(nombre="Cerveza Sin").first()
                else:
                    grupo = [producto]
                    barril_ref = producto

                if barril_ref:
                    litros_actuales = barril_ref.litros_disponibles or Decimal("0")
                    nuevo_valor = max(litros_actuales - litros_a_restar, Decimal("0"))
                    for p in grupo:
                        p.litros_disponibles = nuevo_valor
                        p.save()

            elif not producto.es_barril:
                producto.cantidad = max(producto.cantidad - cantidad, 0)
                producto.save()

    return redirect('lista_pedidos')


def registrar_entrada(request):
    # Cerrar cualquier registro activo antes de iniciar uno nuevo
    RegistroHorario.objects.filter(camarero=request.user, activo=True).update(activo=False, hora_salida=now())

    # Crear un nuevo registro con hora de entrada actual
    RegistroHorario.objects.create(camarero=request.user)
    
    messages.success(request, "Hora de entrada registrada. Cronómetro iniciado.")
    return redirect('control_horarios')

@login_required
def registrar_salida(request):
    registro = RegistroHorario.objects.filter(camarero=request.user, activo=True).first()
    if registro:
        registro.hora_salida = now()
        registro.activo = False  # Marcar el turno como finalizado
        registro.save()
        messages.success(request, "Hora de salida registrada. Cronómetro reiniciado.")
    else:
        messages.error(request, "No tienes un turno activo.")

    return redirect('control_horarios')

@login_required
def control_horarios(request):
    registros = RegistroHorario.objects.filter(camarero=request.user).order_by('-hora_entrada')
    return render(request, 'control_horarios.html', {'registros': registros})

@login_required
def actualizar_nota_producto(request, pedido_id, producto_pedido_id):
    pedido_producto = get_object_or_404(PedidoProducto, id=producto_pedido_id, pedido_id=pedido_id)

    if request.method == "POST":
        nueva_nota = request.POST.get("nota", "").strip()
        pedido_producto.nota = nueva_nota
        pedido_producto.save()
        messages.success(request, "Nota actualizada correctamente.")

    return redirect('detalles_pedido', pedido_id=pedido_id)




