# platform_api/walmart_ca/products.py
from typing import List, Dict, Any
from platform_api.walmart_ca.api import WalmartCAPlatform

class WalmartProducts:
    def __init__(self, client: WalmartCAPlatform) -> None:
        """
        Initialize the Walmart Products module.
        Args:
            client: An instance of the WalmartCAPlatform.
        """
        self.client = client

    def fetch_products(self, include_details: bool = True, limit: int = 50, offset: int = 0, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch products from Walmart Canada.
        Args:
            include_details: Whether to include detailed product info.
            limit: Number of products per page.
            offset: Pagination offset.
            kwargs: Any additional parameters.
        Returns:
            A list of raw product dictionaries.
        """
        endpoint = "items"
        params = {"includeDetails": str(include_details).lower(), "limit": limit, "offset": offset}
        # Merge in any additional options (from extra_options, etc.)
        params.update(kwargs)
        response = self.client.make_request("GET", endpoint, params=params)
        return response.get("items", [])

    def fetch_product_by_sku(self, sku: str) -> Dict[str, Any]:
        """
        Fetch a single product using its SKU.
        This uses the endpoint: https://marketplace.walmartapis.com/v3/ca/items/{sku}
        Args:
            sku: The SKU of the product to fetch.
        Returns:
            A dictionary containing the product details.
        """
        # print(f"Fetching product with SKU: {sku}")
        endpoint = f"items/{sku}"
        response = self.client.make_request("GET", endpoint)
        # If additional parameters are needed, pass them here.
        if "ItemResponse" in response and response["ItemResponse"]:
            return response["ItemResponse"][0]
        return response


