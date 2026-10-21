from decimal import Decimal
from django.db import models


class Restaurante(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    ciudad = models.CharField(max_length=80)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    capacidad = models.IntegerField(default=50)

    class Meta:
        db_table = "restaurantes"

    def __str__(self):
        return self.nombre



class Plato(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    disponible = models.BooleanField(default=True)
    ingredientes = models.IntegerField(default=50)

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.PROTECT,
        related_name="platos"
    )

    class Meta:
        db_table = "platos"
        constraints = [
            models.CheckConstraint(
                check=models.Q(precio__gt=0),
                name="ck_platos_precio_positivo"
            )
        ]

    def __str__(self):
        return self.nombre


class Pedido(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PREPARACION = "en_preparacion", "En preparación"
        LISTO = "listo", "Listo"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    id = models.AutoField(primary_key=True)

    cliente = models.CharField(max_length=255, db_index=True)

    restaurante = models.ForeignKey(
        Restaurante,
        on_delete=models.PROTECT,
        related_name="pedidos"
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    fecha = models.DateTimeField(auto_now_add=True)

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    class Meta:
        db_table = "pedidos"
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    estado__in=[
                        "pendiente",
                        "en_preparacion",
                        "listo",
                        "entregado",
                        "cancelado"
                    ]
                ),
                name="ck_pedidos_estado_valido"
            ),
            models.CheckConstraint(
                check=models.Q(total__gte=0),
                name="ck_pedidos_total_no_negativo"
            )
        ]

    def __str__(self):
        return f"Pedido #{self.id} - {self.estado}"



class ItemPedido(models.Model):
    id = models.AutoField(primary_key=True)

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="items"
    )

    plato = models.ForeignKey(
        Plato,
        on_delete=models.PROTECT,
        related_name="items_pedido"
    )

    cantidad = models.IntegerField()

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        db_table = "items_pedido"
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    cantidad__gte=1,
                    cantidad__lte=20
                ),
                name="ck_items_cantidad_valida"
            ),
            models.CheckConstraint(
                check=models.Q(precio_unitario__gte=0),
                name="ck_items_precio_no_negativo"
            )
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.plato.nombre}"