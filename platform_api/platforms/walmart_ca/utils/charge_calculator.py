from decimal import Decimal
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ChargeCalculator:
    """Calculator for handling Walmart CA order charges"""

    @staticmethod
    def calculate_product_charges(charges: list) -> Dict[str, Any]:
        """Calculate product related charges including tax"""
        product_charge = next(
            (charge for charge in charges if charge.get('chargeType') == 'PRODUCT'),
            {}
        )
        
        # Get product price and tax
        charge_amount = product_charge.get('chargeAmount', {})
        base_price = Decimal(str(charge_amount.get('amount', '0.00')))
        currency = charge_amount.get('currency', 'CAD')
        
        # Get product tax
        tax_info = product_charge.get('tax', {})
        tax_amount = Decimal(str(tax_info.get('taxAmount', {}).get('amount', '0.00')))
        tax_name = tax_info.get('taxName', '')

        return {
            'base_price': base_price,
            'tax_amount': tax_amount,
            'tax_name': tax_name,
            'currency': currency,
            'total': base_price + tax_amount
        }

    @staticmethod
    def calculate_shipping_charges(charges: list) -> Dict[str, Any]:
        """Calculate shipping related charges including tax"""
        shipping_charge = next(
            (charge for charge in charges if charge.get('chargeType') == 'SHIPPING'),
            {}
        )
        
        # Get shipping cost and tax
        charge_amount = shipping_charge.get('chargeAmount', {})
        shipping_cost = Decimal(str(charge_amount.get('amount', '0.00')))
        currency = charge_amount.get('currency', 'CAD')
        
        # Get shipping tax
        tax_info = shipping_charge.get('tax', {})
        tax_amount = Decimal(str(tax_info.get('taxAmount', {}).get('amount', '0.00')))
        tax_name = tax_info.get('taxName', '')

        return {
            'shipping_cost': shipping_cost,
            'tax_amount': tax_amount,
            'tax_name': tax_name,
            'currency': currency,
            'total': shipping_cost + tax_amount
        }

    @staticmethod
    def calculate_other_charges(charges: list) -> Dict[str, Any]:
        """Calculate other charges like eco fees"""
        other_charges = []
        
        for charge in charges:
            if charge.get('chargeType') not in ['PRODUCT', 'SHIPPING']:
                charge_amount = charge.get('chargeAmount', {})
                amount = Decimal(str(charge_amount.get('amount', '0.00')))
                currency = charge_amount.get('currency', 'CAD')
                
                tax_info = charge.get('tax', {})
                tax_amount = Decimal(str(tax_info.get('taxAmount', {}).get('amount', '0.00')))
                
                other_charges.append({
                    'type': charge.get('chargeType'),
                    'name': charge.get('chargeName'),
                    'amount': amount,
                    'tax_amount': tax_amount,
                    'currency': currency,
                    'total': amount + tax_amount
                })
        
        return other_charges

    @classmethod
    def calculate_total_charges(cls, charges: list) -> Dict[str, Any]:
        """Calculate all charges and total"""
        product = cls.calculate_product_charges(charges)
        shipping = cls.calculate_shipping_charges(charges)
        other = cls.calculate_other_charges(charges)
        
        subtotal = product['base_price']
        total_tax = product['tax_amount'] + shipping['tax_amount']
        shipping_total = shipping['total']
        other_total = sum(charge['total'] for charge in other)
        
        return {
            'product': product,
            'shipping': shipping,
            'other_charges': other,
            'summary': {
                'subtotal': subtotal,
                'total_tax': total_tax,
                'shipping_total': shipping_total,
                'other_charges_total': other_total,
                'grand_total': subtotal + total_tax + shipping_total + other_total,
                'currency': product['currency']
            }
        }