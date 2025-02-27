from decimal import Decimal
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class PriceFormatter:
    """Centralized price data formatting and calculation"""
    
    @staticmethod
    def format_charge(charge: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single charge entry"""
        charge_amount = charge.get('chargeAmount', {})
        tax_info = charge.get('tax', {})
        
        return {
            'chargeType': charge.get('chargeType'),
            'chargeName': charge.get('chargeName'),
            'amount': str(Decimal(str(charge_amount.get('amount', '0.00')))),
            'currency': charge_amount.get('currency', 'CAD'),
            'tax_amount': str(Decimal(str(tax_info.get('taxAmount', {}).get('amount', '0.00')))),
            'tax_name': tax_info.get('taxName', ''),
            'isDiscount': charge.get('isDiscount', False)
        }

    @classmethod
    def calculate_totals(cls, formatted_charges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate totals from formatted charges"""
        base_total = sum(Decimal(charge['amount']) for charge in formatted_charges)
        tax_total = sum(Decimal(charge['tax_amount']) for charge in formatted_charges)
        shipping_base = sum(Decimal(charge['amount']) for charge in formatted_charges if charge['chargeType'] == 'SHIPPING')
        shipping_tax = sum(Decimal(charge['tax_amount']) for charge in formatted_charges if charge['chargeType'] == 'SHIPPING')
        shipping_total = shipping_base + shipping_tax

        print(f'shipping total in price_formatter: {shipping_total}')
        
        return {
            'base_total': str(base_total),
            'tax_total': str(tax_total),
            'grand_total': str(base_total + tax_total + shipping_total),
            'currency': formatted_charges[0]['currency'] if formatted_charges else 'CAD'
        }

    @classmethod
    def format_price_data(cls, charges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format and calculate all price data"""
        formatted_charges = [cls.format_charge(charge) for charge in charges]
        print(f'formatted_charges in price_formatter: {formatted_charges}')
        totals = cls.calculate_totals(formatted_charges)
        
        return {
            'charges': formatted_charges,
            'totals': totals
        }