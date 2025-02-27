from typing import Dict, List, Optional
from .api import WalmartCAAPI
from ..processors.walmart_ca.product import WalmartProductProcessor

class WalmartCAProducts(WalmartCAAPI):
    """Handles Walmart CA product operations"""

    def __init__(self):
        super().__init__()
        self.processor = WalmartProductProcessor()

    def get_products(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str = None,
        process: bool = True
    ) -> List[Dict]:
        """Fetch products with optional filters"""
        params = {
            'limit': limit,
            'offset': offset
        }
        if status:
            params['status'] = status

        response = self.make_request('GET', 'items', params=params)
        
        if process:
            return [
                self.processor.process_product(item) 
                for item in response.get('items', [])
            ]
        return response

    def get_product(self, sku: str, process: bool = True) -> Dict:
        """Fetch specific product details"""
        response = self.make_request('GET', f'items/{sku}')
        return self.processor.process_product(response) if process else response

    def update_inventory(self, sku: str, quantity: int) -> Dict:
        """Update product inventory"""
        data = {
            'sku': sku,
            'quantity': {
                'amount': quantity,
                'unit': 'EACH'
            }
        }
        return self.make_request('POST', f'inventory', data=data)

    def update_price(self, sku: str, price: float) -> Dict:
        """Update product price"""
        data = {
            'sku': sku,
            'pricing': [{
                'currentPrice': {
                    'currency': 'CAD',
                    'amount': price
                }
            }]
        }
        return self.make_request('POST', f'prices', data=data)