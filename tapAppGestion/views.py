from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User


from django.http import HttpResponse
from .forms import ProductoForm, RegistroForm

@login_required
def index(request):
    return render(request, 'index.html')

def agregar_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('index')
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






