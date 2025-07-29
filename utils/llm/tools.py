from decimal import MAX_EMAX
from typing import Any
from schemas import UserOrders
from utils.orders import Order, OrderItem
from utils.payment import Payments
from loguru import logger 
from ddgs import DDGS
from utils.whatsapp import send_invoice_whatsapp
from dependancies import MAX_RESULTS

def send_invoice(user_order: UserOrders) -> None:
    """
    Using the customer's details and the request to generate an invoice pdf for the order and confirmation.Create it and send it to the user via whatsapp
    Args:
        user_order: List of containing the customer's information such as:
                    qoute_id: str 
                    customer_id: str
                    customer_contact: str
                    garage_id: str
                    name: str
                    location: str
                    items: list[str]
                    quantity: list[float] of each item
                    price: list[float] of the items
                    total: float
                    created_at: datetime
                    payment_status: str
                    payment_date: datetime
    """
    invoice_filename: str=Order(user_order).create_invoice_pdf()
    send_invoice_whatsapp(recipient_number=user_order.customer_contact, invoice_filename=invoice_filename)

def format_quotation(
    quote_id: str,
    cus_id: str,
    garage_id: str,
    name: str,
    location: str,
    items: list[str],
    quantities: list[int],
    prices: list[float],
) -> Order:
    """
    Your only task is to generate a summary of the interaction and the customer's requirements. If any of the values are missing, ask the user kindly

    Args:
          quote_id: Generate a random uniq ID for each quotation generated per interation.
          cus_id: A unique customer id that is given to each user. Similar to IP addresses
          garage_id:A unique garage identifier associated with each user
          name: Name of the customer
          location: Location of the customer for delivery
          items: User order items
          quantities:list of item quantities
          prices: list of item prices
    Returns:
          Order: Validated order object with PDF invoice
    """
    # Validate input lengths
    if not (len(items) == len(quantities) == len(prices)):
        raise ValueError("Items, quantities, and prices must have the same length")

    # Create order items
    order_items = [
        OrderItem(name=item, quantity=qty, price=price)
        for item, qty, price in zip(items, quantities, prices)
    ]

    # Create order
    order: Order = Order(
        quote_id=quote_id,
        cus_id=cus_id,
        garage_id=garage_id,
        name=name,
        location=location,
        items=order_items,
    )

    # Generate invoice
    invoice: Any = order.create_invoice_pdf()
    logger.info(f"Created order {order.quote_id}, invoice at {invoice}")

    return order


def payment_methods(
    receipt_id: str, quote_id: str, total: float, name: str, option: str
) -> Any:
    """
    Your only task is to help the user handle payment and payment relevant information.
    Args:
        receipt_id:Generate a random unique ID for each payment requested
        quote_id: Quote associated with each order
        name: Name of the customer
        total: Sum of the total products of the quantity and the price in each quotation.
        name: Name of the customer
        option: prompt the user for a payment method:
            - Mpesa :Paybill: 111000, Account Number: quote_id,  Amount: order total
            - Airtel :Paybill: 222000, Account Number: quote_id, Amount:total
            - Tkash :Paybill:333000, Account Number: quote_id, Amount:total
            -Bank Card :Request user for the following bank card details:
                1. Name on the card
                2. Account Number
                3. Expiry Date
                4. CVV (on the back of the card)
            and request for {quote_id}, Amount:{Total} to be paid
    """

    new_payment: Payments = Payments(quote_id, receipt_id, total, name, option)
    logger.info(f"the new payment object is {new_payment}")
    return new_payment


# Tool 3: Internet search after low embedding similarity results
def low_similarity(user_message: str, max_results:int=MAX_RESULTS) -> list[dict[str, str]]:
    """
    Your only role is to carry out internet searches using the DuckDuckGo search python tool below specifically when the user wants to compare products or brands and if the query is outside the current scope. Be careful and do not process any harmful or vulgar searches and requests. Give information on the part type, uses, car types it can be used for
        Args:
            user_message:User query that is outside the contained LLM data and CSV data provided.
            max_results: The number of sources the search tool will retrieve
    """
    try:
        return DDGS().text(user_message, max_results=max_results)

        #internet_search_results=DDGS().text(user_message, max_results=max_results)
        #return [internet_search_results[i].get("body") for i in range(max_results)]
    except ValueError as e:
        logger.error(f"Error during web search: {str(e)}")
        raise