from django.db.models.signals import post_save
from django.apps import apps
from warranties.models import Warranty
from django.db import transaction
from decimal import Decimal
from typing import List, Dict, Union, Optional
import json
import logging
from decimal import Decimal, InvalidOperation
logger = logging.getLogger(__name__)


# def calculate_item_price(quantity: int, unit_price: Decimal) -> Decimal:
#     """
#     Calculate basic item price from quantity and unit price.
#     """
#     # Multiply and then round to 2 decimal places.
#     return (Decimal(quantity) * unit_price).quantize(Decimal('0.01'))

# class DecimalEncoder(json.JSONEncoder):
#     """Custom JSON encoder that converts Decimal to string."""
#     def default(self, obj):
#         if isinstance(obj, Decimal):
#             return str(obj)
#         return super().default(obj)

# def format_price_data(raw_price_data: Union[Dict, List[Dict]]) -> List[Dict]:
#     """
#     Standardize price data format from various platforms.
    
#     Args:
#         raw_price_data: Price data in various formats.
    
#     Returns:
#         List of standardized charge dictionaries.
#     """
#     formatted_data = []
    
#     # If the data comes in as a string, log an error and return empty.
#     if isinstance(raw_price_data, str):
#         logger.error(f"Received string instead of price data structure: {raw_price_data}")
#         return []
    
#     # If raw_price_data is a dict, check for known structures.
#     if isinstance(raw_price_data, dict):
#         # Simple price structure with a base price.
#         if 'base_price' in raw_price_data:
#             try:
#                 amount = Decimal(str(raw_price_data.get('base_price', '0')))
#             except (InvalidOperation, TypeError) as e:
#                 logger.error(f"Error converting base_price: {e}")
#                 amount = Decimal('0.00')
#             charge = {
#                 'chargeType': 'PRODUCT',
#                 'chargeName': 'ItemPrice',
#                 'amount': str(amount.quantize(Decimal('0.01'))),
#                 'currency': raw_price_data.get('currency', 'CAD'),
#                 'isDiscount': False
#             }
#             tax_details = raw_price_data.get('tax_details', {})
#             if tax_details:
#                 # Handle taxAmount whether it is a dict or a simple value.
#                 tax_amount_raw = tax_details.get('taxAmount', {})
#                 if isinstance(tax_amount_raw, dict):
#                     tax_amount = Decimal(str(tax_amount_raw.get('amount', 0)))
#                 else:
#                     tax_amount = Decimal(str(tax_details.get('taxAmount', 0)))
#                 charge['tax'] = {
#                     'taxName': tax_details.get('taxName', 'UNKNOWN'),
#                     'taxAmount': str(tax_amount.quantize(Decimal('0.01')))
#                 }
#             formatted_data.append(charge)
#             return formatted_data
        
#         # Handle Walmart's nested charge structure.
#         elif 'orderLines' in raw_price_data:
#             order_lines = raw_price_data.get('orderLines', {}).get('orderLine', [])
#             # Ensure we have a list.
#             if not isinstance(order_lines, list):
#                 order_lines = [order_lines]
#             if order_lines:
#                 # Assume charges exist in the first order line.
#                 charges = order_lines[0].get('charges', {}).get('charge', [])
#                 raw_price_data = charges
#         # If there's a 'charge' key, extract it.
#         elif 'charge' in raw_price_data:
#             raw_price_data = raw_price_data['charge']
    
#     # Normalize to a list if not already.
#     if not isinstance(raw_price_data, list):
#         raw_price_data = [raw_price_data]
    
#     for charge in raw_price_data:
#         if not isinstance(charge, dict):
#             continue
#         try:
#             # Convert the charge amount to Decimal.
#             charge_amount = Decimal(str(charge.get('chargeAmount', {}).get('amount', 0)))
#             formatted_charge = {
#                 'chargeType': charge.get('chargeType', 'UNKNOWN'),
#                 'chargeName': charge.get('chargeName', 'UNKNOWN'),
#                 'amount': str(charge_amount.quantize(Decimal('0.01'))),
#                 'currency': charge.get('chargeAmount', {}).get('currency', 'CAD'),
#                 'isDiscount': bool(charge.get('isDiscount', False))
#             }
#             if 'tax' in charge:
#                 tax_info = charge['tax']
#                 if isinstance(tax_info.get('taxAmount'), dict):
#                     tax_amount = Decimal(str(tax_info.get('taxAmount', {}).get('amount', 0)))
#                 else:
#                     tax_amount = Decimal(str(tax_info.get('taxAmount', 0)))
#                 formatted_charge['tax'] = {
#                     'taxName': tax_info.get('taxName', 'UNKNOWN'),
#                     'taxAmount': str(tax_amount.quantize(Decimal('0.01')))
#                 }
#             formatted_data.append(formatted_charge)
#         except Exception as e:
#             logger.error(f"Error formatting charge {charge}: {str(e)}")
#             continue
#     print(f'Formatted price data: {formatted_data}')
#     return formatted_data

# def calculate_total_from_price_data(price_data: List[Dict]) -> Decimal:
#     """
#     Calculate the total price including taxes from price data.
    
#     Args:
#         price_data: List of standardized charge dictionaries.
    
#     Returns:
#         Total amount as a Decimal.
#     """
#     total = Decimal('0.00')
#     taxes = Decimal('0.00')

#     for charge in price_data:
#         if charge.get('isDiscount', False):
#             continue

#         try:
#             amount = Decimal(str(charge.get('amount', 0)))
#             total += amount
#         except (InvalidOperation, TypeError) as e:
#             logger.error(f"Error processing amount in charge {charge}: {e}")
#             continue

#         tax_info = charge.get('tax', {})
#         if tax_info:
#             try:
#                 tax_amount = Decimal(str(tax_info.get('taxAmount', 0)))
#                 taxes += tax_amount
#             except (InvalidOperation, TypeError) as e:
#                 logger.error(f"Error processing tax amount in charge {charge}: {e}")
#                 continue

#     return (total + taxes).quantize(Decimal('0.01'))

# def extract_price_components(price_data: List[Dict]) -> Dict[str, Decimal]:
#     """
#     Extract price components handling different charge types.
    
#     Returns a dictionary with:
#         - subtotal: sum of PRODUCT or ItemPrice charges
#         - shipping: shipping charges
#         - tax: total tax
#         - discounts: sum of discount amounts
#         - total: computed as (subtotal + shipping + tax - discounts)
#     """
#     components = {
#         'subtotal': Decimal('0.00'),
#         'tax': Decimal('0.00'),
#         'shipping': Decimal('0.00'),
#         'discounts': Decimal('0.00')
#     }

#     for charge in price_data:
#         try:
#             amount = Decimal(str(charge.get('amount', 0)))
#         except (InvalidOperation, TypeError) as e:
#             logger.error(f"Error processing amount in charge {charge}: {e}")
#             continue
        
#         # Process discounts.
#         if charge.get('isDiscount', False):
#             components['discounts'] += amount
#         # Process shipping charges.
#         elif charge.get('chargeType', '').upper() == 'SHIPPING':
#             components['shipping'] += amount
#         # Process product/item prices.
#         elif charge.get('chargeType', '').upper() in ['PRODUCT', 'ITEMPRICE']:
#             components['subtotal'] += amount
        
#         # Add tax amounts if available.
#         tax_info = charge.get('tax', {})
#         if tax_info:
#             try:
#                 tax_amount = Decimal(str(tax_info.get('taxAmount', 0)))
#                 components['tax'] += tax_amount
#             except (InvalidOperation, TypeError) as e:
#                 logger.error(f"Error processing tax amount in charge {charge}: {e}")
#                 continue

#     # Calculate final total.
#     components['total'] = (
#         components['subtotal'] + 
#         components['shipping'] + 
#         components['tax'] - 
#         components['discounts']
#     ).quantize(Decimal('0.01'))

#     return components
