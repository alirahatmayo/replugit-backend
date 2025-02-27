from datetime import datetime, timedelta
import requests
from django.conf import settings

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

    def get_auth_headers(self, url: str, method: str = "GET") -> dict:
        token = self.get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}