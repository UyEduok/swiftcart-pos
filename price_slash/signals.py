from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import ExpiringProduct, DamageProduct
import json

def broadcast_update(data):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        "inventory_group",
        {
            "type": "product_update",
            "message": json.dumps(data),
        }
    )

# --- Expiring Product ---
@receiver(post_save, sender=ExpiringProduct)
def expiring_product_changed(sender, instance, created, **kwargs):
    data = {
        "id": instance.id,
        "reference": instance.reference or "",
        "product": instance.product.id if instance.product else None,
        "product_name": instance.product_name or "",
        "initial_unit_price": float(instance.initial_unit_price or 0),
        "resale_price": float(instance.resale_price or 0),
        "quantity": instance.quantity or 0,
        "loss_value": float(instance.loss_value or 0),
        "staff_name": instance.staff_name or "",
        "created_date": instance.created_date.strftime("%Y-%m-%d %H:%M:%S") if instance.created_date else "",
        "note": instance.note or "",
        "description": instance.description or "",
        "type": "expiring",
        "created": created
    }
    broadcast_update(data)

@receiver(post_delete, sender=ExpiringProduct)
def expiring_product_deleted(sender, instance, **kwargs):
    broadcast_update({"id": instance.id, "type": "expiring", "deleted": True})

# --- Damaged Product ---
@receiver(post_save, sender=DamageProduct)
def damaged_product_changed(sender, instance, created, **kwargs):
    data = {
        "id": instance.id,
        "reference": instance.reference or "",
        "product": instance.product.id if instance.product else None,
        "product_name": instance.product_name or "",
        "initial_unit_price": float(instance.initial_unit_price or 0),
        "resale_price": float(instance.resale_price or 0),
        "quantity": instance.quantity or 0,
        "loss_value": float(instance.loss_value or 0),
        "staff_name": instance.staff_name or "",
        "created_date": instance.created_date.strftime("%Y-%m-%d %H:%M:%S") if instance.created_date else "",
        "note": instance.note or "",
        "description": instance.description or "",
        "type": "damaged",
        "created": created
    }
    broadcast_update(data)

@receiver(post_delete, sender=DamageProduct)
def damaged_product_deleted(sender, instance, **kwargs):
    broadcast_update({"id": instance.id, "type": "damaged", "deleted": True})
