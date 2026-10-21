
from django.contrib import admin
from .models import Restaurante, Plato, Pedido, ItemPedido


@admin.register(Restaurante)
class RestauranteAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "ciudad", "capacidad")
    search_fields = ("nombre", "ciudad")


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "restaurante", "precio", "disponible")
    list_filter = ("disponible", "restaurante")
    search_fields = ("nombre",)


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido

    extra = 0
    can_delete = False

    fields = ("plato", "cantidad", "precio_unitario")
    readonly_fields = ("plato", "cantidad", "precio_unitario")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cliente",
        "restaurante",
        "estado",
        "fecha",
        "total",
    )

    list_filter = ("estado", "restaurante")
    search_fields = ("cliente",)

    readonly_fields = (
        "cliente",
        "restaurante",
        "fecha",
        "total",
    )

    inlines = [ItemPedidoInline]

    def has_add_permission(self, request):
        return False
