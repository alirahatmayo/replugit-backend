import os
import subprocess
from uuid import uuid4
from datetime import datetime, timedelta
import requests
from django.conf import settings
from .utils.signature import generate_signature

class WalmartCAAuth:
    """Handles Walmart CA API authentication"""

    def __init__(self):
        self.client_id = settings.WALMART_CA_CLIENT_ID
        self.private_key = settings.WALMART_CA_PRIVATE_KEY
        self.channel_type = settings.WALMART_CA_CHANNEL_TYPE
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

    def get_auth_headers(self, url: str, method: str = "GET") -> dict:
        """Generate authentication headers for API requests"""
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
            "WM_QOS.CORRELATION_ID": str(uuid4()),
            "WM_SEC.AUTH_SIGNATURE": signature,
            "WM_SEC.TIMESTAMP": timestamp,
            "WM_CONSUMER.ID": self.client_id,
        }
