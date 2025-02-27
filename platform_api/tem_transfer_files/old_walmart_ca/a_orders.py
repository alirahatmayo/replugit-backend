from platform_api.walmart_ca.api import WalmartCAPlatform

class WalmartOrders:
    def __init__(self, client: WalmartCAPlatform) -> None:
        self.client = client

    def fetch_orders(self, **kwargs):
        return self.client.fetch_orders(**kwargs)

    def fetch_order_by_id(self, order_id: str):
        if not order_id:
            raise ValueError("Order ID is required.")
        endpoint = f"orders/{order_id}"
        return self.client.make_request("GET", endpoint)

    def acknowledge_order(self, order_id: str):
        if not order_id:
            raise ValueError("Order ID is required.")
        endpoint = f"orders/{order_id}/acknowledge"
        return self.client.make_request("POST", endpoint)

    def cancel_order(self, order_id: str, reason: str, sub_reason: str):
        if not order_id or not reason or not sub_reason:
            raise ValueError("Order ID, reason, and sub-reason are required.")
        endpoint = f"orders/{order_id}/cancel"
        data = {"reason": reason, "subReason": sub_reason}
        return self.client.make_request("POST", endpoint, data=data)

    def refund_order(self, order_id: str, refund_data: dict):
        if not order_id or not refund_data:
            raise ValueError("Order ID and refund data are required.")
        endpoint = f"orders/{order_id}/refund"
        return self.client.make_request("POST", endpoint, data=refund_data)

    def get_shipping_updates(self, order_id: str):
        if not order_id:
            raise ValueError("Order ID is required.")
        endpoint = f"orders/{order_id}/shipping"
        return self.client.make_request("GET", endpoint)
