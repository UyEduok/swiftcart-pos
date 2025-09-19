from django.db.models import Sum
from django.utils.timezone import now
from .models import SaleItem, Sale 
import os
import win32api
import win32print

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from io import BytesIO

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from django.conf import settings

def generate_receipt(sale_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo.png')

    # --- Draw faint watermark (behind everything) ---
    c.saveState()  # Save current canvas state
    c.setFillAlpha(0.05)  # Very faint watermark
    c.drawImage(
        logo_path,
        width/2 - 250, height/2 - 250,  # center page
        width=500, height=500,
        preserveAspectRatio=True,
        mask='auto'
    )
    c.restoreState()  # Restore normal opacity

    # --- Top-left logo (bigger) ---
    top_logo_width = 200
    top_logo_height = 140
    c.drawImage(
        logo_path,
        40, height - 90,  # top-left corner
        width=top_logo_width,
        height=top_logo_height,
        preserveAspectRatio=True,
        mask='auto'
    )

    # --- Company name + address + phone (centered) ---
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 50, "Mac-Onella")

    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, height - 65, "74 Woji Road, Rumurulu, Port Harcourt, Rivers State.")
    c.drawCentredString(width/2, height - 80, "Phone: 08109802115, 08105759394, 07064112128")

    c.line(40, height - 90, width - 40, height - 90)

    # --- Receipt info ---
    y = height - 110
    c.setFont("Helvetica", 9)
    c.drawString(40, y, f"Receipt No: {sale_data['receipt_no']}")
    c.drawString(220, y, f"Cashier: {sale_data['cashier_name']}")
    c.drawRightString(width - 40, y, sale_data['datetime'])

    y -= 15
    c.drawString(40, y, f"Customer: {sale_data['customer_name']}")
    c.drawString(220, y, f"Phone: {sale_data.get('customer_phone', 'N/A')}")

    c.line(40, y-10, width - 40, y-10)
    y -= 30

    # --- Items table header (with gray background) ---
    c.setFillColor(colors.lightgrey)
    c.rect(40, y, width-80, 18, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(45, y+5, "No")
    c.drawString(70, y+5, "Item Description")
    c.drawRightString(300, y+5, "Qty")
    c.drawRightString(400, y+5, "Unit Price")
    c.drawRightString(width - 50, y+5, "Amount")

    # --- Items table rows (alternate shading) ---
    y -= 20
    c.setFont("Helvetica", 9)
    for i, item in enumerate(sale_data['items'], start=1):
        if i % 2 == 0:
            c.setFillColorRGB(0.95, 0.95, 0.95)
            c.rect(40, y, width-80, 15, stroke=0, fill=1)
            c.setFillColor(colors.black)

        c.drawString(45, y+3, str(i))
        c.drawString(70, y+3, item['description'][:35])
        c.drawRightString(300, y+3, str(item['qty']))
        c.drawRightString(400, y+3, f"{item['unit_price']:,.2f}")
        c.drawRightString(width - 50, y+3, f"{item['amount']:,.2f}")
        y -= 18

    # --- Totals ---
    y -= 10
    c.line(40, y, width - 40, y)
    y -= 15
    c.setFont("Helvetica", 9)
    c.drawRightString(400, y, "Subtotal:")
    c.drawRightString(width - 50, y, f"{sale_data['subtotal']:,.2f}")
    y -= 15
    c.drawRightString(400, y, "VAT (7.5%):")
    c.drawRightString(width - 50, y, f"{sale_data['vat']:,.2f}")
    y -= 15
    c.drawRightString(400, y, "Discount:")
    c.drawRightString(width - 50, y, f"{sale_data['discount']:,.2f}")
    y -= 15
    c.line(40, y, width - 40, y)
    y -= 20

    # --- Grand total ---
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(400, y, "GRAND TOTAL:")
    c.drawRightString(width - 50, y, f"{sale_data['grand_total']:,.2f}")

    # --- Footer ---
    y -= 40
    c.setFont("Helvetica", 8)
    c.drawString(40, y, f"Reference: {sale_data['reference']}")
    y -= 20
    c.drawCentredString(width/2, y, "Thank you for shopping with us!")
    y -= 12
    c.drawCentredString(width/2, y, "Goods once sold cannot be returned.")
    y -= 20
    c.line(150, y, width - 150, y)
    y -= 12
    c.drawCentredString(width/2, y, "Authorized Signature")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer








def get_cashier_sales_summary(user):
    today = now().date()
    summary = {
        'total_sales': 0,
        'top_product': {},
        'payment_type_amounts': {'Cash': 0, 'Card': 0, 'Transfer': 0}
    }

    try:
        sale_items = SaleItem.objects.filter(
            sale__staff=user,
            sale__sale_date__date=today
        ).select_related('product', 'sale')

        # Total sales
        total_sales = sale_items.aggregate(total=Sum('amount'))['total'] or 0
        summary['total_sales'] = total_sales

        # Top product (most quantity sold)
        top_product = (
            sale_items
            .values('product__name')
            .annotate(total_qty=Sum('quantity'))
            .order_by('-total_qty')
            .first()
        )
        summary['top_product'] = top_product or {}

        # Amount per payment_type
        payment_type_amounts = (
            sale_items
            .values('sale__payment_type')
            .annotate(amount=Sum('amount'))
        )
        for item in payment_type_amounts:
            summary['payment_type_amounts'][item['sale__payment_type']] = item['amount']

    except Exception as e:
        print("Error generating cashier summary:", e)

    return summary



def print_pdf_file(file_path, printer_name=None):
    """
    Automatically print a PDF file to a system printer.

    Args:
        file_path (str): Path to the PDF file to print.
        printer_name (str, optional): Name of the printer. 
                                      Defaults to system default printer.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Use default printer if none specified
    if printer_name is None:
        printer_name = win32print.GetDefaultPrinter()

    # Print PDF silently using the default PDF viewer
    win32api.ShellExecute(
        0,
        "print",
        file_path,
        f'/d:"{printer_name}"',
        ".",
        0
    )
