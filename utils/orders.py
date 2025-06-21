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


class Orders:
    def __init__(
        self,
        qoute_id: str,
        cus_id: str,
        garage_id: str,
        name: str,
        location: str,
        items: list,
        quantity: list,
        price: list,
        total: float,
        created_at: Any,
        payment_status: str,
        payment_date: Any,
    ):
        self.quote_id = qoute_id
        self.cus_id = cus_id
        self.garage_id = garage_id
        self.name = name
        self.location = location
        self.items = items
        self.quantity = quantity
        self.price = price
        self.total = total
        self.created_at = created_at
        self.payment_status = payment_status
        self.payment_date = payment_date
        pass

    def __str__(self) -> str:
        return f"Order{self.quote_id}\nCustomer ID:{self.cus_id}\nGarage ID:{self.garage_id}\nnName:{self.name}\nLocation:{self.location}\nItems:{self.items}\nTotal:ksh. {self.total}\nCreated at:{self.created_at}\nPayemnt Status:{self.payment_status}\nPayment Date:{self.payment_date}"

    def create_invoice_pdf(self, logo_path="../assets/media/logo.png"):
        """
        Create a PDF invoice for an auto parts company

        Parameters:
        -----------
        quote_id : str
            Unique identifier for the quotation
        cus_id:str
            Unique identifier for the customer
        garage_id:str
            Unique identifier for the garage
        name : str
            Customer name
        location : str
            Customer location/address
        items : list or str
            List of items or string of items being purchased
        quantity : list or str
            List of quantities or string of quantities for each item
        total : float or str
            Total amount for the invoice
        price : float or str
            Price per item or total price
        created_at:str
            Date and time when the order was placed
        payment_status:str
            Shows the state of the payment of the order:
                1. Pending - order has been created and awaiting for payment
                2. Paid - order has been paid for
        payment_date: str
            Shows the date of when all/the final payments have been made
        output_path : str, optional
            Path where the PDF will be saved, defaults to "invoice.pdf"
        logo_path : str, optional
            Path to the company logo image file

        Returns:
        --------
        str
            Path to the generated PDF file
        """
        # Create the PDF document
        output_path = f"../assets/data/{self.quote_id}.pdf"
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()

        # Create custom styles
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

        # Initialize elements list for the PDF
        elements = []

        # Add logo if provided
        if logo_path and os.path.exists(logo_path):
            logo = Image(logo_path)
            logo.drawHeight = 1.75 * inch
            logo.drawWidth = 1.75 * inch
            elements.append(logo)
            elements.append(Spacer(1, 0.25 * inch))
        else:
            # Add placeholder for logo
            elements.append(Paragraph("<b>AUTO PARTS COMPANY</b>", title_style))
            elements.append(Spacer(1, 0.25 * inch))

        # Add current date
        current_date = datetime.now().strftime("%B %d, %Y")
        elements.append(Paragraph(f"<b>Date:</b> {current_date}", normal_style))
        elements.append(Spacer(1, 0.25 * inch))

        # Add invoice title
        elements.append(Paragraph("INVOICE / QUOTATION", header_style))
        elements.append(Spacer(1, 0.25 * inch))

        # Add customer information
        customer_info = [
            ["Quotation ID:", self.quote_id],
            ["Customer Name:", self.name],
            ["Location:", self.location],
        ]

        customer_table = Table(customer_info, colWidths=[1.5 * inch, 4 * inch])
        customer_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(customer_table)
        elements.append(Spacer(1, 0.5 * inch))

        # Format items and quantities for the table
        if isinstance(self.items, list) and isinstance(self.quantity, list):
            # If they are lists, create multiple rows
            item_data = [["Item", "Quantity", "Price", "Amount"]]

            # Ensure self.price is a list or convert to one
            if not isinstance(self.price, list):
                # Assuming same self.price for all items
                price_list = [self.price] * len(self.items)
            else:
                price_list = self.price

            # Create rows for each item
            total_amount = 0
            for i in range(len(self.items)):
                if i < len(self.quantity) and i < len(price_list):
                    item_price = (
                        float(price_list[i])
                        if isinstance(price_list[i], str)
                        else price_list[i]
                    )
                    qty = (
                        int(self.quantity[i])
                        if isinstance(self.quantity[i], str)
                        else self.quantity[i]
                    )
                    amount = item_price * qty
                    total_amount += amount
                    item_data.append(
                        [self.items[i], str(qty), f"{item_price:.2f}", f"{amount:.2f}"]
                    )

            # Add total row
            item_data.append(["", "", "Total", f"ksh. {total_amount:.2f}"])
        else:
            # If they are strings, create a simple table
            item_data = [
                ["Item", "Quantity", "self.price(ksh.)", "Total(ksh.)"],
                [self.items, self.quantity, f"{self.price}", f"{self.total}"],
            ]

        # Create the items table
        items_table = Table(
            item_data, colWidths=[2.5 * inch, 1 * inch, 1.5 * inch, 1.5 * inch]
        )
        items_table.setStyle(
            TableStyle(
                [
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
                ]
            )
        )
        elements.append(items_table)
        elements.append(Spacer(1, 0.1 * inch))

        # Add terms and conditions
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

        # Add thank you note
        # elements.append(Spacer(1, 0.3 * inch))
        # elements.append(Paragraph("Thank you for your business!", title_style))

        # Build the PDF
        doc.build(elements)

        # Return the path to the PDF
        return output_path
