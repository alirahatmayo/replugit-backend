from typing import Dict, Any
from .base_product import BaseProductProcessor
import re

class WalmartCAProductProcessor(BaseProductProcessor):
    """Walmart CA specific product processor"""

    def extract_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from Walmart CA format"""
        name = product_data.get('productName', '')
        
        specs = {
            'ram': self._extract_ram(name),
            'storage': self._extract_storage(name),
            'screen_size': self._extract_screen_size(name),
            'processor': self._extract_processor(name)
        }
        
        return {
            'sku': product_data['sku'],
            'name': name,
            'platform': 'walmart_ca',
            'specifications': specs,
            'brand': self._extract_brand(name),
            'is_active': True,
            'platform_specific_data': product_data
        }

    def _extract_ram(self, name: str) -> str:
        ram_pattern = r'(\d+)\s*(?:GB|Go)\s*(?:RAM|DDR\d)?'
        if match := re.search(ram_pattern, name, re.IGNORECASE):
            return f"{match.group(1)}GB"
        return ""

    def _extract_storage(self, name: str) -> str:
        storage_pattern = r'(\d+)\s*(?:GB|Go|TB|To)\s*(?:SSD|HDD)?'
        if match := re.search(storage_pattern, name, re.IGNORECASE):
            return match.group(0)
        return ""

    def _extract_screen_size(self, name: str) -> str:
        screen_pattern = r'(\d+(?:\.\d+)?)\s*(?:"|Pouces?|inch(?:es)?)'
        if match := re.search(screen_pattern, name, re.IGNORECASE):
            return f"{match.group(1)}\""
        return ""

    def _extract_processor(self, name: str) -> str:
        processor_patterns = [
            r'Intel\s+Core\s+[im]\d[-\s]+\d{4,}[A-Z]*',
            r'Intel\s+Core\s+[im]\d+(?:-\d+)?[A-Z]*',
            r'AMD\s+Ryzen\s+\d+\s+\d{4}[A-Z]*'
        ]
        
        for pattern in processor_patterns:
            if match := re.search(pattern, name, re.IGNORECASE):
                return match.group(0)
        return ""

    def _extract_brand(self, name: str) -> str:
        brands = ['HP', 'Dell', 'Lenovo', 'ThinkPad', 'ASUS']
        for brand in brands:
            if brand.lower() in name.lower():
                return brand
        return ""