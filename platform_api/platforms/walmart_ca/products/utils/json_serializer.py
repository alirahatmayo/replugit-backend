"""Utilities for JSON serialization of product data"""
from decimal import Decimal
from typing import Any, Dict, List, Union

class JsonSerializer:
    """Handle JSON serialization for product data"""
    
    @staticmethod
    def convert_for_json(data: Any) -> Any:
        """
        Convert data types to JSON-serializable values
        
        Args:
            data: Any Python data structure with potential Decimal values
            
        Returns:
            Data structure with values that can be JSON serialized
        """
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, dict):
            return {k: JsonSerializer.convert_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [JsonSerializer.convert_for_json(i) for i in data]
        elif data is None or isinstance(data, (str, int, float, bool)):
            return data
        else:
            # For any other types, convert to string 
            return str(data)