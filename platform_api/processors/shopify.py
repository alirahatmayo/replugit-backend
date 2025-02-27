from typing import Dict
from .base import PlatformProcessor

class ShopifyProcessor(PlatformProcessor):
    """Handles Shopify-specific order processing"""
    
    def standardize_order_data(self, order_data: Dict) -> Dict:
        return {
            'platform_order_id': str(order_data['id']),
            'order_number': order_data['order_number'],
            'customer': {
                'name': f"{order_data['customer']['first_name']} {order_data['customer']['last_name']}",
                'email': order_data['customer']['email'],
                'phone': order_data['customer'].get('phone', '')
            },
            'items': [
                {
                    'sku': item['sku'],
                    'quantity': int(item['quantity']),
                    'price_data': {
                        'item_price': float(item['price']),
                        'shipping': float(order_data.get('shipping_lines', [{}])[0].get('price', 0)),
                        'tax': float(item.get('tax_lines', [{}])[0].get('price', 0))
                    }
                } for item in order_data['line_items']
            ],
            'platform_data': order_data
        }

    def standardize_status_update(self, status_data: Dict) -> Dict:
        status_mapping = {
            'fulfilled': 'shipped',
            'cancelled': 'cancelled',
            'delivered': 'delivered'
        }
        
        return {
            'platform_order_id': str(status_data['order_id']),
            'new_state': status_mapping.get(status_data['status'], 'created')
        }
