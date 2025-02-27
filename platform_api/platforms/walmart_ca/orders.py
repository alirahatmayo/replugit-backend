from datetime import datetime
from typing import Dict, List, Optional
from .api import WalmartCAAPI

class WalmartCAOrders(WalmartCAAPI):
    """Handles Walmart CA order operations"""

    def get_orders(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        status: str = None
    ) -> List[Dict]:
        """Fetch orders with optional filters"""
        params = {
            'limit': limit
        }
        
        if start_date:
            params['createdStartDate'] = start_date.strftime('%Y-%m-%d')
        if end_date:
            params['createdEndDate'] = end_date.strftime('%Y-%m-%d')
        if status:
            params['status'] = status

        return self.make_request('GET', 'orders', params=params)

    def get_order(self, order_id: str) -> Dict:
        """Fetch specific order details"""
        return self.make_request('GET', f'orders/{order_id}')

    def acknowledge_order(self, order_id: str) -> Dict:
        """Acknowledge order receipt"""
        return self.make_request('POST', f'orders/{order_id}/acknowledge')

    def ship_order(self, order_id: str, shipment_data: Dict) -> Dict:
        """Mark order as shipped"""
        return self.make_request(
            'POST', 
            f'orders/{order_id}/shipping',
            data=shipment_data
        )