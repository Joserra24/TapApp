from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User
from django.utils.timezone import now



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
def crear_pedido(request):
    categoria_seleccionada = request.GET.get('categoria', None)
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.usuario = request.user
            pedido.save()
            form.save_m2m()  # Guardar la relación many-to-many

            # Guardar las cantidades de los productos
            for producto in form.cleaned_data['productos']:
                cantidad = form.cleaned_data.get(f'cantidad_{producto.id}', 1)
                pedido.productos.add(producto, through_defaults={'cantidad': cantidad})

            messages.success(request, 'El pedido ha sido creado.')
            return redirect('index')
    else:
        form = PedidoForm()
    
    productos_por_categoria = {}
    for producto in Producto.objects.all().order_by('categoria'):
        if producto.categoria not in productos_por_categoria:
            productos_por_categoria[producto.categoria] = []
        productos_por_categoria[producto.categoria].append(producto)
    
    categorias = list(productos_por_categoria.keys())
    productos = productos_por_categoria.get(categoria_seleccionada, []) if categoria_seleccionada else []

    return render(request, 'crear_pedido.html', {
        'form': form,
        'productos_por_categoria': productos_por_categoria,
        'categorias': categorias,
        'productos': productos,
        'categoria_seleccionada': categoria_seleccionada
    })

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

@login_required
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



