from datetime import datetime, timedelta
# import jwt
import requests
from django.conf import settings
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
from uuid import uuid4
from .utils.signature import generate_signature
import json

class WalmartCAAuth:
    def __init__(self):
        self.client_id = settings.WALMART_CA_CLIENT_ID
        self.client_secret = settings.WALMART_CA_CLIENT_SECRET
        self._access_token = None
        self._token_expiry = None

    def get_access_token(self) -> str:
        if not self._is_token_valid():
            self._refresh_token()
        return self._access_token

    def _is_token_valid(self) -> bool:
        return (
            self._access_token is not None and
            self._token_expiry is not None and
            datetime.now() < self._token_expiry
        )

    def _refresh_token(self):
        response = requests.post(
            settings.WALMART_CA_AUTH_URL,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
        )
        if response.status_code != 200:
            raise Exception("Authentication failed for Walmart CA")
        data = response.json()
        self._access_token = data['access_token']
        expires_in = int(data.get('expires_in', 3600))
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in)

    def get_auth_headers(self, url: str, method: str) -> Dict[str, str]:
        """Generate authentication headers for Walmart CA API requests"""
        access_token = self.get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "WM_SVC.NAME": "Walmart Marketplace",
            "WM_QOS.CORRELATION_ID": "123456abcdef",
            "WM_SEC.TIMESTAMP": str(int(datetime.now().timestamp() * 1000)),
            "WM_CONSUMER.ID": self.client_id,
            "WM_CONSUMER.CHANNEL.TYPE": "7d0e5f9a-1d7b-4b5a-9e0d-1a0c9e1a0f0c",
            "Content-Type": "application/json"
        }

class WalmartCAAPI:
    """Base Walmart CA API client"""
    
    BASE_URL = "https://marketplace.walmartapis.com/v3/ca"

    def __init__(self):
        self.client_id = settings.WALMART_CA_CLIENT_ID
        self.private_key = settings.WALMART_CA_CLIENT_SECRET
        self.channel_type = settings.WALMART_CA_CHANNEL_TYPE
#         WALMART_CA_CLIENT_SECRET = config('WALMART_CA_CLIENT_SECRET', default='')
# WALMART_CA_CLIENT_ID = config('WALMART_CA_CLIENT_ID', default='') 
# WALMART_CA_CHANNEL_TYPE = config('WALMART_CA_CHANNEL_TYPE', default='') 
# WALMART_CA_AUTH_URL = config('WALMART_CA_AUTH_URL', default='https://marketplace.walmartapis.com/v3/ca')  

    def _get_headers(self, url: str, method: str) -> Dict[str, str]:
        """Generate authenticated headers for requests"""
        signature, timestamp = generate_signature(
            url=url,
            method=method,
            client_id=self.client_id,
            private_key=self.private_key
        )

        return {
            "WM_SVC.NAME": "Walmart Marketplace",
            "WM_CONSUMER.CHANNEL.TYPE": self.channel_type,
            "WM_TENANT_ID": "WALMART.CA",
            "WM_LOCALE_ID": "en_CA",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_QOS.CORRELATION_ID": str(uuid4()),
            "WM_SEC.AUTH_SIGNATURE": signature,
            "WM_SEC.TIMESTAMP": timestamp,
            "WM_CONSUMER.ID": self.client_id
        }

    def fetch_orders(
        self, 
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        order_id: Optional[str] = None
    ) -> List[Dict]:
        """Fetch orders from Walmart CA API"""
        if order_id:
            return self.make_request('GET', f'orders/{order_id}')

        # Base parameters
        params = {
            'limit': str(limit)
        }
        
        if created_after:
            params['createdStartDate'] = f"{created_after}T00:00:00.000Z"
        
        if created_before:
            params['createdEndDate'] = f"{created_before}T23:59:59.999Z"
        
        if status and status != 'all':
            params['status'] = status.upper()

        print(f'\nRequest Parameters:')
        print(json.dumps(params, indent=2))

        response = self.make_request('GET', 'orders', params=params)
        
        # Handle Walmart CA response structure
        if isinstance(response, dict):
            # Navigate through nested structure: list -> elements -> order
            orders = (response.get('list', {})
                     .get('elements', {})
                     .get('order', []))
            
            if orders:
                print(f'\nFound {len(orders)} orders')
                return orders
            print('\nNo orders found in response')
            
        return []

    def make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Walmart CA API"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        print(f'\nRequest Details:')
        print(f'URL: {url}')
        
        if params:
            query = urlencode(params)
            url = f"{url}{'&' if '?' in url else '?'}{query}"
            print(f'URL with params: {url}')

        headers = self._get_headers(url, method)
        print(f'Headers: {json.dumps(headers, indent=2)}')

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=30
            )
            print(f'\nResponse Status: {response.status_code}')
            
            data = response.json()
            
            # More detailed response structure logging
            if isinstance(data, dict):
                if 'list' in data:
                    list_data = data['list']
                    meta = list_data.get('meta', {})
                    print(f'\nMeta Information:')
                    print(f'- Total Count: {meta.get("totalCount")}')
                    print(f'- Limit: {meta.get("limit")}')
                    print(f'- Next Cursor: {meta.get("nextCursor")}')
                    
                    elements = list_data.get('elements', {})
                    orders = elements.get('order', [])
                    print(f'- Orders Found: {len(orders)}')
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f'\nError Details:')
            if hasattr(e, 'response') and e.response is not None:
                print(f'Error Status: {e.response.status_code}')
                print(f'Error Headers: {dict(e.response.headers)}')
                print(f'Error Body: {e.response.text}')
            raise RuntimeError(f"API request failed: {str(e)}")

    def get_orders(self, **params):
        """Get orders from Walmart CA"""
        return self.make_request("GET", "orders", params=params)

    def get_order(self, order_id: str):
        """Get specific order details"""
        return self.make_request("GET", f"orders/{order_id}")

    # Add other API methods as needed
