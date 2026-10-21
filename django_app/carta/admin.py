
from decimal import Decimal

from django import forms
from django.contrib import admin

from .models import Restaurante, Plato, Pedido, ItemPedido


@admin.register(Restaurante)
class RestauranteAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "ciudad", "capacidad")
    search_fields = ("nombre", "ciudad")


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "restaurante",
        "precio",
        "disponible",
    )
    list_filter = ("disponible", "restaurante")
    search_fields = ("nombre",)


class ItemPedidoForm(forms.ModelForm):
    class Meta:
        model = ItemPedido
        fields = ("cantidad",)

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]

        if not 1 <= cantidad <= 20:
            raise forms.ValidationError(
                "La cantidad debe estar entre 1 y 20."
            )

        return cantidad


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    form = ItemPedidoForm

    extra = 0
    can_delete = False

    fields = ("plato", "cantidad", "precio_unitario")

    # Cantidad queda editable.
    readonly_fields = ("plato", "precio_unitario")

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

    def save_related(self, request, form, formsets, change):
        # Primero guardar las cantidades editadas.
        super().save_related(request, form, formsets, change)

        pedido = form.instance

        # Recalcular usando los precios historicos.
        items = ItemPedido.objects.filter(pedido=pedido)

        nuevo_total = sum(
            (
                item.cantidad * item.precio_unitario
                for item in items
            ),
            Decimal("0.00")
        )

        # Actualizar el total sin permitir su edicion manual.
        Pedido.objects.filter(pk=pedido.pk).update(
            total=nuevo_total
        )

        pedido.total = nuevo_total
