import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BaseAPIClient:
    """
    Base class for platform API clients. Handles common request logic.
    """
    BASE_URL = ''
    TIMEOUT = 10

    def __init__(self, headers=None):
        if not self.BASE_URL:
            raise ValueError("BASE_URL must be set in the subclass.")
        self.headers = headers or {}

    def request(self, method, endpoint, params=None, data=None, timeout=None):
        url = f"{self.BASE_URL}{endpoint}"
        timeout = timeout or self.TIMEOUT
        session = requests.Session()

        # Retry logic
        retry = Retry(
            total=3,  # Total retry attempts
            backoff_factor=0.3,  # Delay between retries
            status_forcelist=[500, 502, 503, 504],  # Retry on specific HTTP errors
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        print(f"Request URL: {url}")
        print(f"Request Headers: {self.headers}")
        print(f"Request Params: {params}")

        try:
            response = session.request(
                method=method, url=url, headers=self.headers, params=params, json=data, timeout=timeout
            )
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"HTTPError: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"RequestException: {str(e)}")
            raise RuntimeError(f"RequestException: {str(e)}")
