from django.db import models
from django.contrib.auth.models import User

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

    def __str__(self):
        return self.nombre

class Pedido(models.Model):
    TIPO_PLATO = (
        ('Entrante', 'Entrante'),
        ('Primer plato', 'Primer plato'),
        ('Segundo plato', 'Segundo plato'),
    )
    
    mesa = models.CharField(max_length=50)  # Número o nombre de la mesa
    numero_clientes = models.PositiveIntegerField()
    camarero = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    cerrado = models.BooleanField(default=False)  # Indica si el pedido está cerrado

    def __str__(self):
        return f'Pedido {self.id} - Mesa {self.mesa}'

class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    nota = models.TextField(blank=True, null=True)
    tipo_plato = models.CharField(max_length=20, choices=Pedido.TIPO_PLATO, blank=True, null=True)

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'
