from .api import WalmartCAAPI
from platform_api.base import BasePlatform  # Absolute import
from platform_api.platforms.walmart_ca.inventory import update_inventory, sync_inventory, \
                                                      sync_all_inventory, get_inventory, get_inventory_status, \
                                                      get_low_stock_items

class WalmartCA(BasePlatform):
    """Main Walmart CA platform integration class"""
    
    def __init__(self):
        self.api = WalmartCAAPI()
        
        # Import here and create the facades
        from .orders import WalmartCAOrders
        from .products import WalmartCAProducts
        
        self.orders = WalmartCAOrders(self.api)
        self.products = WalmartCAProducts(self.api)
        self.inventory = WalmartCAInventory(self.api)  # New inventory interface
    
    # Implement required abstract methods
    def fetch_products(self, *args, **kwargs):
        """Fetch products from Walmart CA"""
        # Implement this or delegate to another class
        raise NotImplementedError("Product fetching not implemented yet")
    
    def format_order(self, order_data, *args, **kwargs):
        """Format order data"""
        # This could delegate to your orders processor
        return self.orders.processor.process_order(order_data)
    
    def format_product(self, product_data, *args, **kwargs):
        """Format product data"""
        # Implement product formatting
        return product_data  # Basic implementation
    
    def get_auth_headers(self):
        """Get authorization headers"""
        # Delegate to the API client which already handles this
        return self.api.get_headers()
    
    # Your existing method
    def fetch_orders(self, *args, **kwargs):
        """Forward to orders.get_orders for backward compatibility"""
        return self.orders.get_orders(*args, **kwargs)

class WalmartCAInventory:
    """Inventory operations for Walmart CA"""
    
    def __init__(self, client):
        self.client = client
        
    def get_inventory(self, sku):
        return get_inventory(self.client, sku)
        
    def update_inventory(self, items):
        return update_inventory(self.client, items)
        
    def sync_inventory(self, sku):
        return sync_inventory(self.client, sku)
        
    def sync_all_inventory(self):
        return sync_all_inventory(self.client)
        
    def get_inventory_status(self, sku):
        return get_inventory_status(self.client, sku)
        
    def get_low_stock_items(self, threshold=5):
        return get_low_stock_items(self.client, threshold)