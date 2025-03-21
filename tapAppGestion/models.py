from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
import datetime


class Producto(models.Model):
    CATEGORIAS = (
        ('Cervezas', 'Cervezas'),
        ('Bebida/Refresco', 'Bebida/Refresco'),
        ('Copa Vino', 'Copa Vino'),
        ('Botellas Vino', 'Botellas Vino'),
        ('Fuera de Carta', 'Fuera de Carta'),
        ('Pan', 'Pan'),
        ('Tapas o ½ Ración', 'Tapas o ½ Ración'),
        ('Entrantes', 'Entrantes'),
        ('Pescados', 'Pescados'),
        ('Carnes Ibéricas', 'Carnes Ibéricas'),
        ('Carnes Ternera', 'Carnes Ternera'),
        ('Bocadillos', 'Bocadillos'),
        ('Postres', 'Postres'),
        ('Cafés', 'Cafés'),
        ('Bebidas Alcohólicas', 'Bebidas Alcohólicas'),
        ('Desayunos', 'Desayunos'),
        ('Oferta del día', 'Oferta del día'),
    )
    
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS)
    precio = models.DecimalField(max_digits=6, decimal_places=2)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    cantidad = models.PositiveIntegerField(default=0)  # Campo para la cantidad en el almacén

    def __str__(self):
        return self.nombre

class Pedido(models.Model):
    mesa = models.CharField(max_length=50)  
    numero_clientes = models.PositiveIntegerField()
    productos = models.ManyToManyField(Producto, through='PedidoProducto')
    camarero = models.ForeignKey(User, on_delete=models.CASCADE)  # Nuevo campo: camarero que toma el pedido
    pagado = models.BooleanField(default=False)  # Nuevo campo
    fecha = models.DateTimeField(default=now)  # Set default to current timestamp
    fecha_cierre = models.DateTimeField(null=True, blank=True)  # Fecha cuando se pagó


    def __str__(self):
        return f'Pedido {self.id} - Mesa {self.mesa} - {self.camarero.username}'

class PedidoProducto(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre} en Pedido {self.pedido.id}'
