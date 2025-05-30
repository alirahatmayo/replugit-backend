from typing import List, Dict, Any
from .get import get_orders, get_order
from .acknowledge import acknowledge_order
from .ship import ship_order
from .cancel import cancel_order
from .utils import get_order_line_numbers
from .processor import WalmartCAOrderProcessor as OrderProcessor

class WalmartCAOrders:
    """Order operations for Walmart CA platform"""
    
    def __init__(self, api):
        self.api = api
    
    def get_orders(self, **kwargs):
        """Get orders with parameters"""
        from .get import get_orders
        return get_orders(self.api, **kwargs)
    
    def get_all_orders(self, **kwargs):
        """Get all orders with pagination"""
        from .get import get_all_orders
        return get_all_orders(self.api, **kwargs)
    
    def acknowledge_order(self, purchase_order_id: str, line_numbers: List[str] = None):
        """Acknowledge receipt of an order"""
        from .acknowledge import acknowledge_order
        return acknowledge_order(self.api, purchase_order_id, line_numbers)
    
    def ship_order(self, purchase_order_id: str, shipping_info: List[Dict[str, Any]]):
        """Update order with shipping information"""
        from .ship import ship_order
        return ship_order(self.api, purchase_order_id, shipping_info)
    
    def cancel_order(self, purchase_order_id: str, cancellations: List[Dict[str, Any]]):
        """Cancel order lines"""
        from .cancel import cancel_order
        return cancel_order(self.api, purchase_order_id, cancellations)
        
    def get_order_line_numbers(self, *args, **kwargs):
        return get_order_line_numbers(*args, **kwargs)
    


# Add to a startup file like __init__.py or settings.py
import builtins
original_str = builtins.str
import platform_api.platforms.walmart_ca.orders.cancel  # Import the problem module

# Check if str is still callable
if not callable(builtins.str):
    print("WARNING: str builtin was overridden. Restoring...")
    builtins.str = original_str