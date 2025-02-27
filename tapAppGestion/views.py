from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages  
from django.contrib.auth.models import User


from django.http import HttpResponse
from .forms import ProductoForm, RegistroForm, EditProfileForm

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

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil ha sido actualizado.')
            return redirect('profile')
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







