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
    es_barril = models.BooleanField(default=False)  # Nuevo campo
    litros_disponibles = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

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
    nota = models.TextField(blank=True, null=True)  # Nuevo campo para notas


    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre} en Pedido {self.pedido.id}'


class RegistroHorario(models.Model):
    camarero = models.ForeignKey(User, on_delete=models.CASCADE)
    hora_entrada = models.DateTimeField(default=now)
    hora_salida = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)  # Indica si el turno está activo

    def calcular_duracion(self):
        if self.hora_salida:
            duracion = self.hora_salida - self.hora_entrada
            segundos = int(duracion.total_seconds())  # Convertir a segundos enteros
            return str(datetime.timedelta(seconds=segundos))  # Formato hh:mm:ss
        return None

    def __str__(self):
        return f"{self.camarero.username} - {self.hora_entrada} a {self.hora_salida}"