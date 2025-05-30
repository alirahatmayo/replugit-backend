class WalmartCAProducts:
    """Product operations for Walmart CA platform"""
    
    def __init__(self, api):
        self.api = api
    
    def get_products(self, **kwargs):
        """Get products with parameters"""
        from .get import get_products
        return get_products(self.api, **kwargs)
    
    def get_all_products(self, **kwargs):
        """Get all products with pagination"""
        from .get import get_all_products
        return get_all_products(self.api, **kwargs)
        
    def update_inventory(self, items):
        """Update inventory levels"""
        from .inventory import update_inventory
        return update_inventory(self.api, items)
        
    def update_price(self, items):
        """Update product prices"""
        from .price import update_price
        return update_price(self.api, items)