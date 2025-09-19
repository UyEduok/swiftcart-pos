from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Product
import json

def broadcast_update(data):
    """
    Helper to send a message to the inventory_group
    """
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        "inventory_group",
        {
            "type": "product_update",  # matches the consumer method
            "message": json.dumps(data),
        }
    )

@receiver(post_save, sender=Product)
def product_changed(sender, instance, created, **kwargs):
    vat_value = float(instance.vat_value or 0)
    unit_price = float(instance.unit_price or 0)
    discount = float(instance.discount or 0)
    discount_quantity = instance.discount_quantity or 0

    data = {
        "id": instance.id,
        "name": instance.name or "",
        "product_code": instance.product_code or "",
        "apply_vat": instance.apply_vat or False,
        "vat_value": vat_value,
        "discount_quantity": discount_quantity,
        "unit_price": unit_price,
        "description": instance.description or "",
        "discount": discount,
        "created": created
    }
    broadcast_update(data)

@receiver(post_delete, sender=Product)
def product_deleted(sender, instance, **kwargs):
    data = {
        "id": instance.id,
        "deleted": True
    }
    broadcast_update(data)
