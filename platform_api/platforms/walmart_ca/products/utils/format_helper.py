"""Utilities for formatting product identifiers and other data"""
from typing import Dict, Any, Optional
import re

class FormatHelper:
    """Formatting helpers for product data"""

    @staticmethod
    def clean_product_name(name: str) -> str:
        """
        Clean product name by removing special characters and normalizing spacing
        
        Args:
            name: Original product name
            
        Returns:
            Cleaned product name
        """
        if not name:
            return ""
            
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', name)
        
        # Remove HTML entities
        cleaned = re.sub(r'&[a-zA-Z]+;', ' ', cleaned)
        
        # Remove excessive punctuation at beginning/end
        cleaned = cleaned.strip('.,;:!?-_"\'')
        
        return cleaned.strip()
    
    @staticmethod
    def extract_brand_from_product_name(name: str) -> Optional[str]:
        """
        Try to extract brand name from product name
        
        Args:
            name: Product name
            
        Returns:
            Potential brand name or None if not determinable
        """
        if not name:
            return None
            
        # Common pattern is brand at the beginning
        parts = name.split()
        if len(parts) >= 1:
            potential_brand = parts[0]
            # Only return if not generic word
            generic_words = ["new", "the", "a", "an", "best", "premium", "quality"]
            if potential_brand.lower() not in generic_words and len(potential_brand) > 1:
                return potential_brand
                
        return None