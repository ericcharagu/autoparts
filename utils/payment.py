class Payments:
    def __init__(
        self,
        quote_id: str,
        receipt_id: str,
        total: float,
        name: str,
        option: str,
    ) -> None:
        self.quote_id = quote_id
        self.id = receipt_id
        self.name = name
        self.total = total
        self.option = option

    def __str__(self) -> str:
        return f"Receipt Number:{self.id}\nQuoute Number:{self.quote_id}\nName:{self.name}\nAmount:{self.total}"
