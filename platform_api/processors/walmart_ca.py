from typing import Dict
# from .base import PlatformProcessor
from base import PlatformProcessor

class WalmartCAProcessor(PlatformProcessor):
    def standardize_order_data(self, order_data: Dict) -> Dict:
        return {
            'platform_order_id': f"CA-{order_data['purchaseOrderId']}",
            'order_number': f"CA-{order_data['customerOrderId']}",
            'customer': {
                'name': order_data['shippingInfo']['postalAddress']['name'],
                'email': order_data.get('customerEmailId', ''),
                'phone': order_data['shippingInfo']['phone']
            },
            'items': [
                {
                    'sku': f"CA-{item['sku']}",
                    'quantity': int(item['quantity']),
                    'price_data': {
                        'item_price': float(item['itemPrice']['amount']),
                        'shipping': float(item.get('shippingPrice', {}).get('amount', 0)),
                        'tax': float(item.get('tax', {}).get('amount', 0))
                    }
                } for item in order_data['orderLines']['orderLine']
            ],
            'platform_data': order_data
        }
    
    def standardize_status_update(self, status_data: Dict) -> Dict:
        status_mapping = {
            'Shipped': 'shipped',
            'Cancelled': 'cancelled',
            'Delivered': 'delivered'
        }
        return {
            'platform_order_id': f"CA-{status_data['purchaseOrderId']}",
            'new_state': status_mapping.get(status_data['status'], 'created')
        }