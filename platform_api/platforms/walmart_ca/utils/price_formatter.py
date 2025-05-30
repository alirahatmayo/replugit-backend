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
    def format_canadian_taxes(cls, charges: List[Dict]) -> Dict[str, Any]:
        """Format Canadian taxes (GST, HST, PST, QST)"""
        tax_summary = {
            'GST': Decimal('0'),  # Federal
            'HST': Decimal('0'),  # Combined (specific provinces)
            'PST': Decimal('0'),  # Provincial
            'QST': Decimal('0'),  # Quebec
            'ECO': Decimal('0'),  # Eco fees
            'OTHER': Decimal('0')  # Other taxes
        }
        
        for charge in charges:
            tax_name = charge.get('tax', {}).get('taxName', '')
            tax_amount = Decimal(str(charge.get('tax', {}).get('taxAmount', {}).get('amount', '0')))
            
            if tax_name == 'GST':
                tax_summary['GST'] += tax_amount
            elif tax_name == 'HST':
                tax_summary['HST'] += tax_amount
            elif tax_name == 'PST':
                tax_summary['PST'] += tax_amount
            elif tax_name == 'QST':
                tax_summary['QST'] += tax_amount
            elif 'Eco' in tax_name or 'Environmental' in tax_name:
                tax_summary['ECO'] += tax_amount
            elif tax_amount > 0:
                tax_summary['OTHER'] += tax_amount
        
        # Remove zero taxes
        return {k: str(v) for k, v in tax_summary.items() if v > 0}

    @classmethod
    def format_price_data(cls, charges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format complete price data including totals and taxes"""
        formatted_charges = []
        total_amount = Decimal('0.00')
        total_tax = Decimal('0.00')
        currency = 'CAD'
        shipping_total = Decimal('0.00')
        product_total = Decimal('0.00')

        for charge in charges:
            formatted = cls.format_charge(charge)
            formatted_charges.append(formatted)
            
            amount = Decimal(formatted['amount'])
            tax = Decimal(formatted['tax_amount'])
            
            if formatted['chargeType'] == 'SHIPPING':
                shipping_total += amount + tax
            elif formatted['chargeType'] == 'PRODUCT':
                product_total += amount + tax
                
            total_amount += amount
            total_tax += tax
            currency = formatted['currency']  # Use last non-empty currency
        
        # Format Canadian taxes
        tax_summary = cls.format_canadian_taxes(charges)
        
        # Print debug info
        if formatted_charges:
            print(f"formatted_charges in price_formatter: {formatted_charges}")
        if shipping_total > 0:
            print(f"shipping total in price_formatter: {shipping_total}")
            
        return {
            'charges': formatted_charges,
            'totals': {
                'base_total': str(total_amount),
                'tax_total': str(total_tax),
                'grand_total': str(total_amount + total_tax),
                'shipping_total': str(shipping_total),
                'product_total': str(product_total),
                'currency': currency
            },
            'tax_summary': tax_summary
        }