from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import Pedido, Producto, PedidoProducto

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio']

class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo Electrónico")
    first_name = forms.CharField(max_length=30, required=True, label="Nombre")
    last_name = forms.CharField(max_length=30, required=True, label="Apellido")

    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="", 
    )

    password2 = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="",
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]
        help_texts = {"username": None, "password1": None, "password2": None,}     

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user

class EditProfileForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="",
        required=False,
    )

    password2 = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="",
        required=False,
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        help_texts = {"username": None,}

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)
        if commit:
            user.save()
        return user

class PedidoForm(forms.ModelForm):
    productos = forms.ModelMultipleChoiceField(
        queryset=Producto.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    cantidades = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Pedido
        fields = ['mesa', 'numero_clientes', 'productos']

    def save(self, commit=True):
        pedido = super().save(commit=False)
        if commit:
            pedido.save()
            productos = self.cleaned_data['productos']
            cantidades = self.cleaned_data.get('cantidades', '{}')

            import json
            cantidades_dict = json.loads(cantidades)

            for producto in productos:
                cantidad = cantidades_dict.get(str(producto.id), 1)
                PedidoProducto.objects.create(pedido=pedido, producto=producto, cantidad=cantidad)

        return pedido

class ActualizarStockForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['cantidad']
        
        

