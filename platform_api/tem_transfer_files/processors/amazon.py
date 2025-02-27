# import json
# from datetime import datetime
# from typing import Dict
# # from base import PlatformProcessor

# class AmazonProcessor(PlatformProcessor):
#     """
#     Handles Amazon-specific order processing.
#     Simplified to focus on core functionality.
#     """
    
#     def standardize_order_data(self, order_data: Dict) -> Dict:
#         """Convert Amazon order data to standard format"""
#         return {
#             'platform_order_id': order_data['AmazonOrderId'],
#             'order_number': order_data['AmazonOrderId'],
#             'customer': {
#                 'name': order_data['BuyerInfo']['BuyerName'],
#                 'email': order_data['BuyerInfo']['BuyerEmail'],
#                 'phone': order_data['ShippingAddress'].get('Phone', '')
#             },
#             'items': [
#                 {
#                     'sku': item['SellerSKU'],
#                     'quantity': int(item['QuantityOrdered']),
#                     'price_data': {
#                         'item_price': float(item['ItemPrice']['Amount']),
#                         'shipping': float(item.get('ShippingPrice', {}).get('Amount', 0)),
#                         'tax': float(item.get('ItemTax', {}).get('Amount', 0))
#                     }
#                 } for item in order_data['OrderItems']
#             ],
#             'platform_data': order_data
#         }

#     def standardize_status_update(self, status_data: Dict) -> Dict:
#         """Convert Amazon status update to standard format"""
#         status_mapping = {
#             'Shipped': 'shipped',
#             'Canceled': 'cancelled',
#             'Delivered': 'delivered'
#         }
        
#         return {
#             'platform_order_id': status_data['AmazonOrderId'],
#             'new_state': status_mapping.get(status_data['OrderStatus'], 'created')
#         }
