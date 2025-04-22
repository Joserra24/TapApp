from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User
from .models import Pedido, Producto, PedidoProducto, ProductoPagado
from django.utils.timezone import now, localtime, timedelta
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from .models import RegistroHorario
from collections import defaultdict
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models.functions import TruncMonth
from django.template.loader import render_to_string
from io import BytesIO





import calendar
import json


from django.http import HttpResponse
from .forms import ProductoForm, RegistroForm, EditProfileForm, PedidoForm, ActualizarStockForm, RegistroForm
from .models import Producto, Pedido, RegistroHorario


@login_required
def index(request):
    return render(request, 'index.html')

def admin_required(user):
    return user.is_superuser

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
    if not request.user.is_superuser:
        raise PermissionDenied("Solo los administradores pueden editar productos.")
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
    if not request.user.is_superuser:
        raise PermissionDenied("Solo los administradores pueden eliminar productos.")
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'El producto ha sido eliminado.')
        return redirect('menu')
    return render(request, 'confirmacion_eliminar_producto.html', {'producto': producto})


@login_required
def lista_pedidos(request, pedido_id=None):
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

    return render(request, 'lista_pedidos.html', {'pedidos_con_productos': pedidos_con_productos,  'pedido_reciente_id': pedido_id})


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
        total_pedido = pedido.pedidoproducto_set.aggregate(total=Sum(F('producto__precio') * F('cantidad')))['total'] or 0
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
        # Cafés normales
        if producto.categoria == "Cafés" and producto.nombre in ["Café Leche", "Café Solo", "Café Cortado"]:
            producto.cantidad = int((producto.kilos_disponibles or 0) / Decimal("0.008"))

        # Descafeinados
        elif producto.categoria == "Cafés" and producto.nombre in ["Desca Leche", "Desca Cortado", "Desca Solo"]:
            producto.cantidad = int((producto.kilos_disponibles or 0) / Decimal("0.008"))

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
def eliminar_pedido_cerrado(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, pagado=True)

    if request.method == "POST":
        pedido.delete()
        return redirect('lista_pedidos_cerrados')  # Asegúrate que este es el name correcto

    return redirect('lista_pedidos_cerrados')

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
                nota = request.POST.get(f'nota_{producto.id}', '').strip()
                PedidoProducto.objects.create(
                    pedido=pedido,
                    producto=producto,
                    cantidad=cantidad,
                    nota=nota if nota else None
                )

            return redirect('lista_pedidos_confirmado', pedido_id=pedido.id)
    else:
        form = PedidoForm()
    
    productos = Producto.objects.all().order_by('categoria')
    categorias = {}
    for producto in productos:
        # Cafés normales
        if producto.categoria == "Cafés" and producto.nombre in ["Café Leche", "Café Solo", "Café Cortado"]:
            producto.cantidad = int((producto.kilos_disponibles or 0) / Decimal("0.008"))

        # Descafeinados
        elif producto.categoria == "Cafés" and producto.nombre in ["Desca Leche", "Desca Cortado", "Desca Solo"]:
            producto.cantidad = int((producto.kilos_disponibles or 0) / Decimal("0.008"))

        if producto.categoria not in categorias:
            categorias[producto.categoria] = []
        categorias[producto.categoria].append(producto)
    return render(request, 'crear_pedido.html', {'form': form, 'categorias': categorias})

@login_required
@user_passes_test(admin_required)
def stock(request):

    categoria_seleccionada = request.GET.get('categoria', None)

    # Grupos de productos que comparten barril
    barril_grupo_1 = ["Cerveza Con", "Tubo Con", "Cortada", "Cañón"]
    barril_grupo_2 = ["Cerveza Sin", "Tubo Sin"]
    BOCADILLOS_GRUPO = ["Serranito", "Montado de Lomo"]

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
        
        # 2) NUEVO: si la categoría es “Carnes Ibéricas” o “Pescados”, manejamos kilos
        elif producto.categoria in ["Carnes Ibéricas", "Pescados"]:
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    producto.kilos_disponibles = kilos_float
                    producto.save()
                except ValueError:
                    pass

        # 3) Bocadillos => Serranito / Montado => actualizar el grupo entero
        elif producto.categoria == "Bocadillos" and producto.nombre in BOCADILLOS_GRUPO:
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    # Actualizar TODOS los productos en la lista BOCADILLOS_GRUPO
                    relacionados = Producto.objects.filter(
                        categoria="Bocadillos",
                        nombre__in=BOCADILLOS_GRUPO
                    )
                    for p in relacionados:
                        p.kilos_disponibles = kilos_float
                        p.save()
                except ValueError:
                    pass

         # 4) Entrantes en kilogramos
        #    a) Productos individuales: Pollo Kentaky, Patatas Braviolis, Jamón, Queso, Caña Lomo
        elif producto.categoria == "Entrantes" and (producto.nombre == "Pollo Kentaky" or producto.nombre == "Patatas Braviolis" or producto.nombre == "Jamón" or producto.nombre == "Queso" or producto.nombre == "Caña Lomo"):
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    producto.kilos_disponibles = kilos_float
                    producto.save()
                except ValueError:
                    pass

         #    b) Ensaladas que comparten stock: Ensalada de Atún y Ensalada Rulo Cabra
        elif producto.categoria == "Entrantes" and (producto.nombre == "Ensalada Atún" or producto.nombre == "Ensalada Rulo Cabra"):
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    # Actualizamos ambas ensaladas en grupo:
                    relacionados = Producto.objects.filter(categoria="Entrantes", nombre__in=["Ensalada Atún", "Ensalada Rulo Cabra"])
                    for p in relacionados:
                        p.kilos_disponibles = kilos_float
                        p.save()
                except ValueError:
                    pass

         # 5) Entrantes en unidades: Croquetas Gourmet / Croquetas Caseras
        elif producto.categoria == "Entrantes" and (producto.nombre == "Croquetas Gourmet" or producto.nombre == "Croquetas Caseras"):
            form = ActualizarStockForm(request.POST, instance=producto)
            if form.is_valid():
                form.save()

        # 6) Cafés agrupados en kilogramos
        elif producto.categoria == "Cafés" and producto.nombre in ["Café Leche", "Café Solo", "Café Cortado"]:
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    relacionados = Producto.objects.filter(
                        categoria="Cafés",
                        nombre__in=["Café Leche", "Café Solo", "Café Cortado"]
                    )
                    for p in relacionados:
                        p.kilos_disponibles = kilos_float
                        p.save()
                except ValueError:
                    pass

        elif producto.categoria == "Cafés" and producto.nombre in ["Desca Leche", "Desca Cortado", "Desca Solo"]:
            kilos = request.POST.get('kilos_disponibles', None)
            if kilos is not None:
                try:
                    kilos_float = float(kilos)
                    relacionados = Producto.objects.filter(
                        categoria="Cafés",
                        nombre__in=["Desca Leche", "Desca Cortado", "Desca Solo"]
                    )
                    for p in relacionados:
                        p.kilos_disponibles = kilos_float
                        p.save()
                except ValueError:
                    pass
  
        else:
            form = ActualizarStockForm(request.POST, instance=producto)
            if form.is_valid():
                form.save()

        return redirect(f'/stock?categoria={categoria_seleccionada}')

    productos = Producto.objects.exclude(categoria__in=['Pan']).order_by('categoria')
    productos_por_categoria = {}
    for producto in productos:
        if producto.categoria not in productos_por_categoria:
            productos_por_categoria[producto.categoria] = []
        productos_por_categoria[producto.categoria].append(producto)
    
    categorias = list(productos_por_categoria.keys())
    if categoria_seleccionada:
        productos_filtrados = productos_por_categoria.get(categoria_seleccionada, [])
    else:
        productos_filtrados = [p for sublist in productos_por_categoria.values() for p in sublist]
    
    return render(request, 'stock.html', {
        'productos_por_categoria': productos_por_categoria,
        'categorias': categorias,
        'productos_filtrados': productos_filtrados,
        'categoria_seleccionada': categoria_seleccionada
    })


@login_required
def pagar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if not pedido.pagado:
        pedido.pagado = True
        pedido.fecha_cierre = now()
        pedido.save()

        productos_pedido = PedidoProducto.objects.filter(pedido=pedido)

        # Productos con descuento por litros
        conversion_litros = {
            "Cerveza Con": 0.2,
            "Tubo Con": 0.25,
            "Cortada": 0.275,
            "Cañón": 0.350,
            "Cerveza Sin": 0.2,
            "Tubo Sin": 0.25,
            "Radler": 0.2,
        }

        grupo_con = ["Cerveza Con", "Tubo Con", "Cortada", "Cañón"]
        grupo_sin = ["Cerveza Sin", "Tubo Sin"]

        vinos = [
            "Ramón Bilbao Crianza", "Dulce Eva", "Ramón Bilbao Rueda", "Árabe",
            "Viña Pelina", "Habla del Silencio", "Alaude",
            "Ramón Bilbao Reserva", "Marqués de Riscal", "Resalso"
        ]

        RESTA_KILOS = Decimal("0.3")

        bocadillos_descuento = {
            "Serranito": Decimal("0.2"),       # 200 g
            "Montado de Lomo": Decimal("0.1"), # 100 g
        } 

        BOCADILLOS_GRUPO = ["Serranito", "Montado de Lomo"]  # Comparten el mismo stock
  
        total_bocadillos = Decimal("0")

        ENTRANTES_KILOS = ["Pollo Kentaky", "Patatas Braviolis", "Jamón", "Queso", "Caña Lomo"]

        ENSALADAS_GRUPO = ["Ensalada Atún", "Ensalada Rulo Cabra"]

        total_ensaladas = Decimal("0")


        croquetas_descuento = {
            "Croquetas Caseras": 10,
            "Croquetas Gourmet": 10
        }

        for item in productos_pedido:
            producto = item.producto
            cantidad = item.cantidad

            # 🔻 Descuento por litros (cervezas y radler)
            if producto.nombre in conversion_litros:
                litros_por_unidad = Decimal(str(conversion_litros[producto.nombre]))
                litros_a_restar = litros_por_unidad * cantidad

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

            # 🍷 Descuento por copa de vino → resta litros en botella
            elif producto.nombre in vinos:
                litros_actuales = producto.litros_disponibles or Decimal("0")
                total_a_restar = Decimal("0.15") * cantidad
                producto.litros_disponibles = max(litros_actuales - total_a_restar, Decimal("0"))
                producto.save()

            # 🍾 Descuento por unidad al vender botella
            elif producto.nombre.startswith("Botella "):
                producto.cantidad = max(producto.cantidad - cantidad, 0)
                producto.save()

            # 4) ENTRANTES KILOS (individuales) => 0.3 kg cada uno
            elif producto.nombre in ENTRANTES_KILOS:
                kilos_actuales = producto.kilos_disponibles or Decimal("0")
                total_a_restar = Decimal("0.3") * cantidad
                producto.kilos_disponibles = max(kilos_actuales - total_a_restar, Decimal("0"))
                producto.save()

             # 5) ENSALADAS (grupo) => 0.3 kg
            elif producto.nombre in ENSALADAS_GRUPO:
                # Acumulamos la cantidad vendida de ensaladas
                total_a_restar = Decimal("0.3") * cantidad
                total_ensaladas += total_a_restar

             # 6) CROQUETAS => descuenta 10 unidades por 1 croqueta
            elif producto.nombre in croquetas_descuento:
                units_current = producto.cantidad
                # si vendes X croquetas => descuenta X*10
                total_unidades_a_restar = croquetas_descuento[producto.nombre] * cantidad
                producto.cantidad = max(units_current - total_unidades_a_restar, 0)
                producto.save()

            # 4) Descuento para “Carnes Ibéricas” y “Pescados” → 300 g (0.3 kg) por cada unidad vendida
            elif producto.categoria in ["Carnes Ibéricas", "Pescados"]:
                kilos_actuales = producto.kilos_disponibles or Decimal("0")
                total_a_restar = RESTA_KILOS * cantidad  # 0.3 kg * cantidad
                producto.kilos_disponibles = max(kilos_actuales - total_a_restar, Decimal("0"))
                producto.save()

            elif producto.nombre in BOCADILLOS_GRUPO:
                # No lo restamos aún directamente, sino que lo acumulamos
                descuento_por_unidad = bocadillos_descuento[producto.nombre]  # 0.2 o 0.1
                total_bocadillos += descuento_por_unidad * cantidad

            # 7) Descuento para “Cafés” → 8 g (0.008 kg) por cada unidad vendida (grupo común)
            elif producto.nombre in ["Café Leche", "Café Solo", "Café Cortado"]:
                RESTA_CAFE = Decimal("0.008")
                kilos_actuales = producto.kilos_disponibles or Decimal("0")
                total_a_restar = RESTA_CAFE * cantidad
                nuevo_valor = max(kilos_actuales - total_a_restar, Decimal("0"))

                grupo = Producto.objects.filter(nombre__in=["Café Leche", "Café Solo", "Café Cortado"])
                for p in grupo:
                    p.kilos_disponibles = nuevo_valor
                    p.save()

            # 8) Descuento para “Descafeinados” → 8 g (0.008 kg) por cada unidad vendida (grupo común)
            elif producto.nombre in ["Desca Leche", "Desca Cortado", "Desca Solo"]:
                RESTA_DESCAFEINADO = Decimal("0.008")
                kilos_actuales = producto.kilos_disponibles or Decimal("0")
                total_a_restar = RESTA_DESCAFEINADO * cantidad
                nuevo_valor = max(kilos_actuales - total_a_restar, Decimal("0"))

                grupo = Producto.objects.filter(nombre__in=["Desca Leche", "Desca Cortado", "Desca Solo"])
                for p in grupo:
                    p.kilos_disponibles = nuevo_valor
                    p.save()


            # 🧊 Otros productos normales (por unidad)
            elif not producto.es_barril:
                producto.cantidad = max(producto.cantidad - cantidad, 0)
                producto.save()

         # 3) Ahora, tras el bucle, aplicamos la resta acumulada a todo el grupo BOCADILLOS_GRUPO
        if total_bocadillos > 0:
            # Tomamos como referencia uno de ellos (por ejemplo, Serranito) para leer su stock actual
            bocadillo_ref = Producto.objects.filter(nombre__in=BOCADILLOS_GRUPO).first()
            if bocadillo_ref:
                kilos_actuales = bocadillo_ref.kilos_disponibles or Decimal("0")
                nuevo_valor = max(kilos_actuales - total_bocadillos, Decimal("0"))

                # Asignamos ese nuevo valor a todos los productos del grupo
                grupo_bocadillos = Producto.objects.filter(nombre__in=BOCADILLOS_GRUPO)
                for p in grupo_bocadillos:
                    p.kilos_disponibles = nuevo_valor
                    p.save()

        if total_ensaladas > 0:
            # Tomamos un producto de referencia (p.ej. "Ensalada Atún") para leer su stock actual
            ensalada_ref = Producto.objects.filter(nombre__in=ENSALADAS_GRUPO).first()
            if ensalada_ref:
                kilos_actuales = ensalada_ref.kilos_disponibles or Decimal("0")
                nuevo_valor = max(kilos_actuales - total_ensaladas, Decimal("0"))

                # Asignar este valor a todos los del grupo
                grupo_ensaladas = Producto.objects.filter(nombre__in=ENSALADAS_GRUPO)
                for p in grupo_ensaladas:
                    p.kilos_disponibles = nuevo_valor
                    p.save()
                    
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
def exportar_horarios_pdf(request):
    registros = RegistroHorario.objects.filter(camarero=request.user).order_by('hora_entrada')

    # Nombres de meses en español (indexados por mes)
    nombres_meses_es = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    # Agrupar por (año, mes)
    registros_por_mes = defaultdict(list)
    total_por_mes = defaultdict(int)
    total_segundos = 0

    for r in registros:
        duracion = r.calcular_duracion()
        if duracion:
            h, m, s = map(int, str(duracion).split(":"))
            segundos = h * 3600 + m * 60 + s
            total_segundos += segundos

            key = (r.hora_entrada.year, r.hora_entrada.month)
            registros_por_mes[key].append(r)
            total_por_mes[key] += segundos

    total_duracion = str(timedelta(seconds=total_segundos))

    # Crear lista de grupos ordenados y traducidos
    registros_ordenados = []
    for (year, month) in sorted(registros_por_mes):
        nombre_mes = f"{nombres_meses_es[month]} {year}"
        registros_ordenados.append({
            'mes': nombre_mes,
            'registros': registros_por_mes[(year, month)],
            'total_mes': str(timedelta(seconds=total_por_mes[(year, month)]))
        })

    template = get_template('horarios_pdf.html')
    html = template.render({
        'registros_ordenados': registros_ordenados,
        'total_duracion': total_duracion,
        'usuario': request.user,
        'fecha_generacion': now()

    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="horarios.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error al generar el PDF')
    return response

@login_required
def control_horarios(request):
    # Si el usuario es administrador, obtiene todos los registros;
    # en ese caso se permite filtrar por camarero mediante el parámetro GET "camarero".
    if request.user.is_superuser:
        registros = RegistroHorario.objects.all()
        # Obtener el filtro de camarero enviado en el GET (si existe)
        selected_camarero = request.GET.get('camarero', '')
        if selected_camarero:
            registros = registros.filter(camarero__id=selected_camarero)
        camareros = User.objects.filter(registrohorario__isnull=False).distinct()
    else:
        registros = RegistroHorario.objects.filter(camarero=request.user)
        selected_camarero = None
        camareros = None


    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if fecha_inicio:
        registros = registros.filter(hora_entrada__date__gte=parse_date(fecha_inicio))
    if fecha_fin:
        registros = registros.filter(hora_entrada__date__lte=parse_date(fecha_fin))

    registros = registros.order_by('-hora_entrada')

    try:
        registro_activo = RegistroHorario.objects.get(camarero=request.user, activo=True)
    except RegistroHorario.DoesNotExist:
        registro_activo = None

    # Para el filtro por camarero, obtenemos la lista de camareros que tengan al menos un registro.
    # Esto se realiza solo para administradores.
    if request.user.is_superuser:
        camareros = User.objects.filter(registrohorario__isnull=False).distinct()
    else:
        camareros = None

    return render(request, 'control_horarios.html', {
        'registros': registros,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'camareros': camareros,
        'selected_camarero': selected_camarero,
        'registro_activo': registro_activo,
    })

@login_required
def actualizar_nota_producto(request, pedido_id, producto_pedido_id):
    pedido_producto = get_object_or_404(PedidoProducto, id=producto_pedido_id, pedido_id=pedido_id)

    if request.method == "POST":
        nueva_nota = request.POST.get("nota", "").strip()
        pedido_producto.nota = nueva_nota
        pedido_producto.save()
        messages.success(request, "Nota actualizada correctamente.")

    return redirect('detalles_pedido', pedido_id=pedido_id)

@login_required
def generar_ticket_pdf(request, pedido_id):
    pedido = Pedido.objects.get(id=pedido_id)
    productos_pedido = PedidoProducto.objects.filter(pedido=pedido)

    # Categorías que NO deben aparecer en el ticket de cocina
    categorias_excluidas = [
        "Cervezas", "Bebida/Refresco", "Copa Vino", "Botellas Vino", "Bebidas Alcohólicas", "Desayunos"
    ]

    productos_comida = [
        p for p in productos_pedido if p.producto.categoria not in categorias_excluidas
    ]

    template = get_template('ticket_cocina.html')
    html = template.render({
        'pedido': pedido,
        'productos_comida': productos_comida,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_mesa_{pedido.mesa}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('❌ Error al generar el ticket de cocina')
    return response

@login_required
def generar_ticket_cliente(request, pedido_id):
    pedido = Pedido.objects.get(id=pedido_id)
    productos_pedido = PedidoProducto.objects.filter(pedido=pedido)

    total = 0
    for item in productos_pedido:
        item.subtotal = item.cantidad * item.producto.precio
        total += item.subtotal

    template = get_template('ticket_cliente.html')
    html = template.render({
        'pedido': pedido,
        'productos_pedido': productos_pedido,
        'total': total,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_cliente_mesa_{pedido.mesa}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("❌ Error al generar el ticket del cliente")
    return response


@login_required
def pagar_producto(request, pedido_id, producto_pedido_id):
    # Obtenemos la línea del pedido
    producto_pedido = get_object_or_404(PedidoProducto, id=producto_pedido_id, pedido_id=pedido_id)
    producto = producto_pedido.producto
    cantidad_a_pagar = 1  # Solo se procesa 1 unidad

    # --------------------- Lógica de actualización del stock ---------------------
    conversion_litros = {
        "Cerveza Con": 0.2,
        "Tubo Con": 0.25,
        "Cortada": 0.275,
        "Cañón": 0.350,
        "Cerveza Sin": 0.2,
        "Tubo Sin": 0.25,
        "Radler": 0.2,
    }
    grupo_con = ["Cerveza Con", "Tubo Con", "Cortada", "Cañón"]
    grupo_sin = ["Cerveza Sin", "Tubo Sin"]

    vinos = [
        "Ramón Bilbao Crianza", "Dulce Eva", "Ramón Bilbao Rueda", "Árabe",
        "Viña Pelina", "Habla del Silencio", "Alaude",
        "Ramón Bilbao Reserva", "Marqués de Riscal", "Resalso"
    ]
    RESTA_KILOS = Decimal("0.3")

    bocadillos_descuento = {
        "Serranito": Decimal("0.2"),       # 200 g
        "Montado de Lomo": Decimal("0.1"),  # 100 g
    }
    BOCADILLOS_GRUPO = ["Serranito", "Montado de Lomo"]
    total_bocadillos = Decimal("0")

    ENTRANTES_KILOS = ["Pollo Kentaky", "Patatas Braviolis", "Jamón", "Queso", "Caña Lomo"]

    ENSALADAS_GRUPO = ["Ensalada Atún", "Ensalada Rulo Cabra"]
    total_ensaladas = Decimal("0")

    croquetas_descuento = {
        "Croquetas Caseras": 10,
        "Croquetas Gourmet": 10
    }

    if producto.nombre in conversion_litros:
        litros_por_unidad = Decimal(str(conversion_litros[producto.nombre]))
        litros_a_restar = litros_por_unidad * cantidad_a_pagar
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

    elif producto.nombre in vinos:
        litros_actuales = producto.litros_disponibles or Decimal("0")
        total_a_restar = Decimal("0.15") * cantidad_a_pagar
        producto.litros_disponibles = max(litros_actuales - total_a_restar, Decimal("0"))
        producto.save()

    elif producto.nombre.startswith("Botella "):
        producto.cantidad = max(producto.cantidad - cantidad_a_pagar, 0)
        producto.save()

    elif producto.nombre in ENTRANTES_KILOS:
        kilos_actuales = producto.kilos_disponibles or Decimal("0")
        total_a_restar = Decimal("0.3") * cantidad_a_pagar
        producto.kilos_disponibles = max(kilos_actuales - total_a_restar, Decimal("0"))
        producto.save()

    elif producto.nombre in ENSALADAS_GRUPO:
        deduction = Decimal("0.3") * cantidad_a_pagar
        total_ensaladas += deduction
        # Se actualizará el grupo después del bucle

    elif producto.nombre in croquetas_descuento:
        deduction_units = croquetas_descuento[producto.nombre] * cantidad_a_pagar
        producto.cantidad = max(producto.cantidad - deduction_units, 0)
        producto.save()

    elif producto.categoria in ["Carnes Ibéricas", "Pescados"]:
        kilos_actuales = producto.kilos_disponibles or Decimal("0")
        total_a_restar = RESTA_KILOS * cantidad_a_pagar
        producto.kilos_disponibles = max(kilos_actuales - total_a_restar, Decimal("0"))
        producto.save()

    elif producto.categoria == "Bocadillos" and (producto.nombre == "Serranito" or producto.nombre == "Montado de Lomo"):
        deduction = bocadillos_descuento[producto.nombre] * cantidad_a_pagar
        total_bocadillos += deduction

        # 7) Descuento para “Cafés” → 8 g (0.008 kg) por unidad vendida (grupo común)
    elif producto.nombre in ["Café Leche", "Café Solo", "Café Cortado"]:
        RESTA_CAFE = Decimal("0.008")
        kilos_actuales = producto.kilos_disponibles or Decimal("0")
        total_a_restar = RESTA_CAFE * cantidad_a_pagar
        nuevo_valor = max(kilos_actuales - total_a_restar, Decimal("0"))

        grupo = Producto.objects.filter(nombre__in=["Café Leche", "Café Solo", "Café Cortado"])
        for p in grupo:
            p.kilos_disponibles = nuevo_valor
            p.save()

    # 8) Descuento para “Descafeinados” → 8 g (0.008 kg) por unidad vendida (grupo común)
    elif producto.nombre in ["Desca Leche", "Desca Cortado", "Desca Solo"]:
        RESTA_DESCAFEINADO = Decimal("0.008")
        kilos_actuales = producto.kilos_disponibles or Decimal("0")
        total_a_restar = RESTA_DESCAFEINADO * cantidad_a_pagar
        nuevo_valor = max(kilos_actuales - total_a_restar, Decimal("0"))

        grupo = Producto.objects.filter(nombre__in=["Desca Leche", "Desca Cortado", "Desca Solo"])
        for p in grupo:
            p.kilos_disponibles = nuevo_valor
            p.save()



    elif not producto.es_barril:
        producto.cantidad = max(producto.cantidad - cantidad_a_pagar, 0)
        producto.save()

    # Aplicar acumulaciones para grupos:
    if total_bocadillos > 0:
        bocadillo_ref = Producto.objects.filter(nombre__in=BOCADILLOS_GRUPO).first()
        if bocadillo_ref:
            kilos_actuales = bocadillo_ref.kilos_disponibles or Decimal("0")
            nuevo_valor = max(kilos_actuales - total_bocadillos, Decimal("0"))
            grupo_bocadillos = Producto.objects.filter(nombre__in=BOCADILLOS_GRUPO)
            for p in grupo_bocadillos:
                p.kilos_disponibles = nuevo_valor
                p.save()

    if total_ensaladas > 0:
        ensalada_ref = Producto.objects.filter(nombre__in=ENSALADAS_GRUPO).first()
        if ensalada_ref:
            kilos_actuales = ensalada_ref.kilos_disponibles or Decimal("0")
            nuevo_valor = max(kilos_actuales - total_ensaladas, Decimal("0"))
            grupo_ensaladas = Producto.objects.filter(nombre__in=ENSALADAS_GRUPO)
            for p in grupo_ensaladas:
                p.kilos_disponibles = nuevo_valor
                p.save()

    # --------------------- Actualizamos la línea del pedido ---------------------
    # Se resta 1 unidad; si queda 0, se elimina la línea para quitar el producto de la lista.
    ProductoPagado.objects.create(
        producto=producto,
        cantidad=1,
        precio_unitario=producto.precio,
        fecha=localtime(now()).date(),
        pedido=producto_pedido.pedido,
        camarero=request.user
    )
    if producto_pedido.cantidad > 1:
        producto_pedido.cantidad -= 1
        producto_pedido.save()
    else:
        producto_pedido.delete()

    messages.success(request, f"Se ha pagado 1 unidad de {producto.nombre}.")
    return redirect('detalles_pedido', pedido_id=pedido_id)

@login_required
def pausar_jornada(request):
    try:
        registro = RegistroHorario.objects.get(camarero=request.user, activo=True)
        now = timezone.now()
        # Calcular el tiempo transcurrido como timedelta
        elapsed = now - registro.hora_entrada
        registro.tiempo_transcurrido = elapsed  # Asigna el timedelta directamente
        registro.pausado = True
        registro.save()
        messages.success(request, "Jornada pausada correctamente.")
    except RegistroHorario.DoesNotExist:
        messages.error(request, "No tienes un turno activo para pausar.")
    return redirect('control_horarios')

@login_required
def reanudar_jornada(request):
    try:
        registro = RegistroHorario.objects.get(camarero=request.user, activo=True, pausado=True)
        now = timezone.now()
        # Recuperar el tiempo acumulado como timedelta
        paused_duration = registro.tiempo_transcurrido
        # Ajustamos la hora de entrada para que, al calcular la diferencia, se incluya el tiempo ya acumulado
        registro.hora_entrada = now - paused_duration
        registro.pausado = False
        # Reiniciamos el tiempo acumulado para futuras pausas
        registro.tiempo_transcurrido = timedelta(0)
        registro.save()
        messages.success(request, "Jornada reanudada correctamente.")
    except RegistroHorario.DoesNotExist:
        messages.error(request, "No tienes un turno pausado para reanudar.")
    return redirect('control_horarios')

@login_required
def reporte(request):
    # 1) Fecha seleccionada o hoy
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = parse_date(fecha_str)
        except (ValueError, TypeError):
            fecha = localtime(now()).date()
    else:
        fecha = localtime(now()).date()

    # 2) Pedidos pagados esa fecha
    pedidos = Pedido.objects.filter(pagado=True, fecha_cierre__date=fecha)

    # 3) Anotar cantidad y precio unitario, luego total por producto
    ventas = (
        PedidoProducto.objects
            .filter(pedido__in=pedidos)
            .values('producto__categoria',
                    'producto__nombre',
                    'producto__precio')
            .annotate(cantidad=Sum('cantidad'))
            .annotate(
                total=ExpressionWrapper(
                    F('cantidad') * F('producto__precio'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
            .order_by('producto__categoria', 'producto__nombre')
    )

    # 🔄 3.1) Añadir productos pagados individualmente ese día
    pagos_sueltos = ProductoPagado.objects.filter(fecha=fecha)

    # Unificamos ambas fuentes en una lista común
    from collections import defaultdict
    reporte_por_categoria = defaultdict(list)
    contador_productos = defaultdict(lambda: {'cantidad': 0, 'total': 0, 'precio': 0, 'nombre': '', 'categoria': ''})

    # Añadir los productos de pedidos completos
    for v in ventas:
        key = (v['producto__nombre'], v['producto__categoria'])
        contador_productos[key]['cantidad'] += v['cantidad']
        contador_productos[key]['total'] += v['total']
        contador_productos[key]['precio'] = float(v['producto__precio'])
        contador_productos[key]['nombre'] = v['producto__nombre']
        contador_productos[key]['categoria'] = v['producto__categoria']

    # Añadir los productos pagados individualmente
    for pago in pagos_sueltos:
        key = (pago.producto.nombre, pago.producto.categoria)
        contador_productos[key]['cantidad'] += pago.cantidad
        contador_productos[key]['total'] += pago.total()
        contador_productos[key]['precio'] = float(pago.precio_unitario)
        contador_productos[key]['nombre'] = pago.producto.nombre
        contador_productos[key]['categoria'] = pago.producto.categoria

    # 4) Agrupar para el template
    reporte_por_categoria = {}
    # Agrupar por categoría asegurando existencia y orden
    for (nombre, categoria), val in sorted(contador_productos.items(), key=lambda x: (x[1]['categoria'], x[1]['nombre'])):
        if categoria not in reporte_por_categoria:
            reporte_por_categoria[categoria] = []

        reporte_por_categoria[categoria].append({
            'nombre':   nombre,
            'precio':   val['precio'],
            'cantidad': val['cantidad'],
            'total':    val['total'],
        })


    # 5) Datos para la gráfica
    labels = list(reporte_por_categoria.keys())
    values = [
        sum(prod['cantidad'] for prod in items)
        for items in reporte_por_categoria.values()
    ]

    # 6) Producto estrella
    top = max(ventas, key=lambda x: x['cantidad'], default=None)
    top_name  = top['producto__nombre'] if top else None
    top_count = top['cantidad']          if top else 0

    # 7) **Total del día**: suma de todos los totales individuales
    grand_total = sum(item['total'] for item in contador_productos.values())

    # 8) Datos por mes para gráfica de barras
    ventas_mensuales = (
        Pedido.objects.filter(pagado=True)
        .annotate(mes=TruncMonth('fecha_cierre'))
        .values('mes')
        .annotate(total=Sum(F('pedidoproducto__producto__precio') * F('pedidoproducto__cantidad')))
        .order_by('mes')
    )

    # Formatear datos para Chart.js
    meses_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

    bar_labels = [meses_es[v['mes'].month - 1].capitalize() for v in ventas_mensuales]
    bar_values = [float(v['total']) if v['total'] else 0 for v in ventas_mensuales]

    return render(request, 'reporte.html', {
        'fecha': fecha,
        'reporte_por_categoria': reporte_por_categoria,
        'labels': labels,
        'values': values,
        'top_name': top_name,
        'top_count': top_count,
        'grand_total': grand_total,
        'bar_labels': bar_labels,
        'bar_values': bar_values,
    })

@login_required
def reporte_pdf(request):
    # Obtener pedidos pagados
    pedidos = Pedido.objects.filter(pagado=True)

    # Agrupar por día
    ventas_por_dia = (
        pedidos
        .values('fecha_cierre__date')
        .annotate(total=Sum(F('pedidoproducto__producto__precio') * F('pedidoproducto__cantidad')))
        .order_by('fecha_cierre__date')
    )

    # Agrupar por mes
    from django.db.models.functions import TruncMonth
    ventas_por_mes = (
        pedidos
        .annotate(mes=TruncMonth('fecha_cierre'))
        .values('mes')
        .annotate(total=Sum(F('pedidoproducto__producto__precio') * F('pedidoproducto__cantidad')))
        .order_by('mes')
    )

    total_ingresos = sum([v['total'] or Decimal("0") for v in ventas_por_mes])


    # Renderizar HTML
    html = render_to_string('reporte_pdf.html', {
        'ventas_por_dia': ventas_por_dia,
        'ventas_por_mes': ventas_por_mes,
        'now':now(),
        'total_ingresos': total_ingresos,
    })

    # Generar PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_ventas.pdf"'
    pisa_status = pisa.CreatePDF(BytesIO(html.encode("UTF-8")), dest=response)
    
    if pisa_status.err:
        return HttpResponse('Hubo un error generando el PDF', status=500)
    return response