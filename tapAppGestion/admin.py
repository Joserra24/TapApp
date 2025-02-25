from django.contrib import admin

from .models import Producto, Pedido, PedidoItem

# Register your models here.

admin.site.register(Producto)
admin.site.register(Pedido) 
admin.site.register(PedidoItem) 


