from typing import Dict

class PlatformProcessor:
    def standardize_order_data(self, order_data: Dict) -> Dict:
        """Convert platform-specific order data to standard format"""
        raise NotImplementedError
    
    def standardize_status_update(self, status_data: Dict) -> Dict:
        """Convert platform-specific status update to standard format"""
        raise NotImplementedError