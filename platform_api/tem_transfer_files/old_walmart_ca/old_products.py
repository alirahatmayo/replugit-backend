#platform_api/walmart_ca/products.py

from platform_api.walmart_ca.api_client import WalmartCanadaAPIClient


class WalmartProducts:
    def __init__(self, client: WalmartCanadaAPIClient):
        """
        Initialize the Walmart Products module.

        Args:
            client (WalmartCanadaAPIClient): An instance of the Walmart Canada API client.
        """
        self.client = client

    def fetch_products(self, include_details=True, limit=50, offset=0):
        """
        Fetch products with pagination and optional detailed information.

        Args:
            include_details (bool): Whether to include detailed product information.
            limit (int): Number of products per request (if includeDetails is True).
            offset (int): Pagination offset (if includeDetails is True).

        Returns:
            dict: API response containing product details.
        """
        endpoint = "items"
        params = {"includeDetails": str(include_details).lower()}  # Convert boolean to 'true' or 'false'

        # Add pagination parameters only if includeDetails is True
        if include_details:
            params["limit"] = limit
            params["offset"] = offset

        return self.client.make_request("GET", endpoint, params=params)

    def fetch_product_by_sku(self, sku):
        """
        Fetch a specific product by its SKU.

        Args:
            sku (str): SKU of the product.

        Returns:
            dict: API response containing product details.
        """
        if not sku:
            raise ValueError("SKU is required to fetch a specific product.")

        endpoint = f"items/{sku}"
        return self.client.make_request("GET", endpoint)
