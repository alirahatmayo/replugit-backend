from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BasePlatform(ABC):
    """Abstract interface for all marketplace platforms."""

    @abstractmethod
    def fetch_orders(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch orders in standardized format."""
        pass

    @abstractmethod
    def fetch_products(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch products in standardized format."""
        pass

    @abstractmethod
    def format_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw order data to a standardized order format."""
        pass

    @abstractmethod
    def format_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw product data to a standardized product format."""
        pass

    @abstractmethod
    def get_auth_headers(self, **kwargs) -> Dict[str, str]:
        """Return authentication headers for an API call."""
        pass
