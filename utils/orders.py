import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from dotenv import load_dotenv
from typing import Any

# load environment
load_dotenv()


from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
import os
import logging

logger = logging.getLogger(__name__)

SYSTEM_DATE = datetime.now()

class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float

    @property
    def total(self) -> float:
        return self.quantity * self.price

class OrderBase(BaseModel):
    quote_id: str = Field(..., description="Unique quotation ID")
    cus_id: str = Field(..., description="Unique customer ID")
    garage_id: str = Field(..., description="Unique garage identifier")
    name: str = Field(..., description="Customer name")
    location: str = Field(..., description="Delivery location")
    items: List[OrderItem]
    created_at: datetime = Field(default_factory=datetime.now)
    payment_status: str = Field(
        default="pending",
        description="Order status: processing, pending, shipped, delivered"
    )
    payment_date: datetime = Field(
        default_factory=lambda: datetime.now() + timedelta(days=14),
        description="Due payment date (default: 14 days from creation)"
    )

    @validator('payment_status')
    def validate_payment_status(cls, v):
        allowed_statuses = ["processing", "pending", "shipped", "delivered"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v

    @property
    def total(self) -> float:
        return sum(item.total for item in self.items)

    def __str__(self) -> str:
        return (
            f"Order {self.quote_id}\n"
            f"Customer ID: {self.cus_id}\n"
            f"Garage ID: {self.garage_id}\n"
            f"Name: {self.name}\n"
            f"Location: {self.location}\n"
            f"Items: {[item.name for item in self.items]}\n"
            f"Total: ksh. {self.total:.2f}\n"
            f"Created at: {self.created_at}\n"
            f"Payment Status: {self.payment_status}\n"
            f"Payment Date: {self.payment_date}"
        )

class Order(OrderBase):
    def create_invoice_pdf(self, logo_path: str = "../assets/media/logo.png") -> str:
        """Generate a PDF invoice for the order."""
        output_path = f"../assets/data/{self.quote_id}.pdf"
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.darkblue,
            spaceAfter=12,
        )

        header_style = ParagraphStyle(
            "Header",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.darkblue,
            spaceAfter=10,
        )

        normal_style = ParagraphStyle(
            "Normal", parent=styles["Normal"], fontSize=11, spaceBefore=6, spaceAfter=6
        )

        elements = []

        # Add logo or company name
        if logo_path and os.path.exists(logo_path):
            logo = Image(logo_path)
            logo.drawHeight = 1.75 * inch
            logo.drawWidth = 1.75 * inch
            elements.append(logo)
            elements.append(Spacer(1, 0.25 * inch))
        else:
            elements.append(Paragraph("<b>AUTO PARTS COMPANY</b>", title_style))
            elements.append(Spacer(1, 0.25 * inch))

        # Add invoice header
        elements.append(Paragraph(f"<b>Date:</b> {self.created_at.strftime('%B %d, %Y')}", normal_style))
        elements.append(Spacer(1, 0.25 * inch))
        elements.append(Paragraph("INVOICE / QUOTATION", header_style))
        elements.append(Spacer(1, 0.25 * inch))

        # Customer information
        customer_info = [
            ["Quotation ID:", self.quote_id],
            ["Customer Name:", self.name],
            ["Location:", self.location],
        ]

        customer_table = Table(customer_info, colWidths=[1.5 * inch, 4 * inch])
        customer_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(customer_table)
        elements.append(Spacer(1, 0.5 * inch))

        # Items table
        item_data = [["Item", "Quantity", "Price (ksh)", "Amount (ksh)"]]
        for item in self.items:
            item_data.append([
                item.name,
                str(item.quantity),
                f"{item.price:.2f}",
                f"{item.total:.2f}"
            ])

        item_data.append(["", "", "Total", f"{self.total:.2f}"])

        items_table = Table(item_data, colWidths=[2.5 * inch, 1 * inch, 1.5 * inch, 1.5 * inch])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.darkblue),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
            ("LINEBELOW", (0, -2), (-1, -2), 1, colors.black),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 0.1 * inch))

        # Terms and conditions
        elements.append(Paragraph("<b>Terms & Conditions:</b>", normal_style))
        terms = [
            "1. Payment is due within 30 days from the date of invoice.",
            "2. Returns are accepted within 14 days with original packaging.",
            "3. All parts come with a 90-day warranty unless otherwise stated.",
            "4. Prices are subject to change without notice.",
            "5. This quotation is valid for 30 days from the date of issue.",
        ]
        for term in terms:
            elements.append(Paragraph(term, normal_style))

        elements.append(Paragraph("Thank you for your business!", title_style))
        doc.build(elements)

        return f"{self.quote_id}.pdf"
