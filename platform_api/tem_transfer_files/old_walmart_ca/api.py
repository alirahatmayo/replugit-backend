from typing import List, Dict, Any
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
import logging
from django.conf import settings
from ..base import BasePlatform
from .auth import WalmartCAAuth

logger = logging.getLogger(__name__)

class WalmartCAPlatform(BasePlatform):
    """
    Walmart CA Platform implementation.
    Implements the BasePlatform interface.
    """
    def __init__(self) -> None:
        self.base_url: str = getattr(settings, "WALMART_CA_BASE_URL", "https://marketplace.walmartapis.com/v3/ca")
        self.auth = WalmartCAAuth()
        self.session = requests.Session()  # Use persistent session for connection pooling

    def fetch_orders(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch orders from Walmart CA Marketplace"""
        try:
            created_after = kwargs.get("created_after", 
                (datetime.now() - timedelta(days=7)).isoformat())
            
            params = {"createdStartDate": created_after}
            if kwargs.get("created_before"):
                params["createdEndDate"] = kwargs["created_before"]

            logger.info(f"Fetching orders with params: {params}")
            
            response = self.make_request(
                method="GET", 
                endpoint="orders", 
                params=params
            )
            
            # Add debug logging
            logger.debug(f"Raw API response: {response}")
            
            # Navigate the correct response structure
            orders_raw = response.get("list", {}).get("elements", {}).get("order", [])
            if not orders_raw:
                logger.warning("No orders found in response")
                return []
                
            logger.info(f"Found {len(orders_raw)} orders")
            return [self.format_order(order) for order in orders_raw]
            
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise

    def fetch_products(self, **kwargs) -> List[Dict[str, Any]]:
        params = {"includeDetails": str(kwargs.get("include_details", True)).lower()}
        if kwargs.get("include_details", True):
            params["limit"] = kwargs.get("limit", 50)
            params["offset"] = kwargs.get("offset", 0)
        response = self.make_request(method="GET", endpoint="items", params=params)
        # Use the "ItemResponse" wrapper if it exists; otherwise fallback to an empty list.
        if response.get("ItemResponse"):
            items = response["ItemResponse"]
            if isinstance(items, list):
                return items
        return []

    def fetch_product_by_sku(self, sku: str) -> dict:
        """
        Fetch a single product by SKU from Walmart CA.
        Uses the endpoint: /items/{sku}
        """
        endpoint = f"items/{sku}"
        logger.info(f"Fetching single product at endpoint: {self.base_url.rstrip('/')}/{endpoint}")
        response = self.make_request(method="GET", endpoint=endpoint)
        # Check if the response contains an "ItemResponse" wrapper and take the first element.
        if response.get("ItemResponse"):
            items = response["ItemResponse"]
            if isinstance(items, list) and len(items) > 0:
                return items[0]
            print(f"items in fetch_product_by_sku: {items}")
        return response

    def format_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Walmart CA order to common format"""
        logger.debug(f"Formatting order data: {order_data}")  # Add debug logging
        print(f"order_data: {order_data}")
        
        try:
            return {
                "order_number": order_data.get("purchaseOrderId"),
                "customer_order_id": order_data.get("customerOrderId"),
                "order_date": order_data.get("orderDate"),
                "state": self._map_order_state(order_data.get("status")),
                "items": [self._format_order_item(item) 
                         for item in order_data.get("order", {}).get("orderLines", [])],
                "platform": "walmart_ca",
                "platform_specific_data": order_data,
            }
        except Exception as e:
            logger.error(f"Error formatting order: {e}, data: {order_data}")
            raise

    def format_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        print(f"product_data: {product_data}")
        return {
            "sku": product_data.get("sku"),
            "name": product_data.get("productName"),
            "gtin": product_data.get("gtin"),
            "platform": "walmart_ca",
            "platform_specific_data": product_data,
        }

    def get_auth_headers(self, **kwargs) -> Dict[str, str]:
        return self.auth.get_auth_headers(url=kwargs.get("url", ""), method=kwargs.get("method", "GET"))

    def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        if kwargs.get("params"):
            url = f"{url}?{urlencode(kwargs['params'])}"
        headers = self.get_auth_headers(url=url, method=method)
        print(f"url in make request: {url}")
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=kwargs.get("data"),
                timeout=getattr(settings, "WALMART_CA_TIMEOUT", 30),
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("API request failed: %s", e)
            raise RuntimeError(f"API request failed: {e}") from e

    def _map_order_state(self, status: str) -> str:
        status_map = {
            "Created": "pending",
            "Acknowledged": "processing",
            "Shipped": "shipped",
            "Delivered": "delivered",
            "Cancelled": "cancelled",
        }
        return status_map.get(status, "unknown")

    def _format_order_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Format Walmart CA order item to common format"""
        logger.debug(f"Formatting order item: {item}")  # Add debug logging
        
        try:
            if isinstance(item, str):
                logger.error(f"Received string instead of dict for item: {item}")
                return {"error": "Invalid item format", "raw_data": item}
                
            return {
                "sku": item.get("item", {}).get("sku"),
                "quantity": item.get("orderLineQuantity", {}).get("amount"),
                "price": item.get("charges", [{}])[0].get("chargeAmount", {}).get("amount"),
                "status": item.get("status"),
                "raw_item": item  # Include raw data for debugging
            }
        except Exception as e:
            logger.error(f"Error formatting order item: {e}, item: {item}")
            raise
