from django.contrib import admin

from .models import Producto, Pedido, PedidoProducto, RegistroHorario

# Register your models here.

admin.site.register(Producto)
admin.site.register(Pedido) 
admin.site.register(PedidoProducto) 
admin.site.register(RegistroHorario)



