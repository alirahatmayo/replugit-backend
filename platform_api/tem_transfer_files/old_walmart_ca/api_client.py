# platform_api/walmart_ca/api_client.py
# Description: Walmart Canada API client for making authenticated requests to the Walmart Marketplace API.
# Author: Ali Khan
import requests
import subprocess
from uuid import uuid4
from urllib.parse import urlencode
from datetime import datetime, timezone
import os


class WalmartCanadaAPIClient:
    BASE_URL = "https://marketplace.walmartapis.com/v3/ca/"  # Sandbox/Production URL
    SIGNATURE_UTILITY_JAR = "platform_api/walmart_ca/utils/DigitalSignatureUtil-1.0.0.jar"
    TEMP_SIGNATURE_FILE = "platform_api/walmart_ca/temp/temp_signature.txt"  # Temp file for signature output

    def __init__(self, client_id, private_key, channel_type):
        """
        Initialize the Walmart Canada API client.

        Args:
            client_id (str): Walmart-provided Client ID.
            private_key (str): Path to the private key in PKCS#8 format.
            channel_type (str): Walmart Consumer Channel Type.
        """
        self.client_id = client_id
        self.private_key = private_key
        self.channel_type = channel_type

    def _generate_signature(self, url, method, params=None):
        """
        Generate the signature using Walmart's Java utility.

        Args:
            url (str): The full API endpoint URL.
            method (str): HTTP method (e.g., "GET", "POST").
            params (dict): Query parameters.

        Returns:
            tuple: (Base64-encoded signature, Unix timestamp in milliseconds)
        """
 
        # Construct the Java utility command
        command = [
            "java",
            "-jar",
            self.SIGNATURE_UTILITY_JAR,
            "DigitalSignatureUtil",
            url,
            self.client_id,
            self.private_key,
            method.upper(),
            self.TEMP_SIGNATURE_FILE,
        ]
        # print(f"Executing Java Command: {' '.join(command)}")

        # Run the Java utility
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Java Command Failed: {' '.join(command)}")
            raise RuntimeError(f"Error running Java utility: {e.stderr}")

        # Read the signature and timestamp from the temp file
        try:
            with open(self.TEMP_SIGNATURE_FILE, "r") as file:
                lines = file.readlines()
                signature = lines[0].split(":")[1].strip()
                timestamp = lines[1].split(":")[1].strip()
                return signature, timestamp
        except FileNotFoundError:
            raise RuntimeError("Signature utility output file not found. Check permissions or the utility path.")
        finally:
            if os.path.exists(self.TEMP_SIGNATURE_FILE):
                os.remove(self.TEMP_SIGNATURE_FILE)

    def _prepare_headers(self, url, method, params=None):
        """
        Prepare headers with signature and timestamp.

        Args:
            url (str): Full API endpoint URL.
            method (str): HTTP method.
            params (dict): Query parameters.

        Returns:
            dict: Request headers
        """

        print(f"url from prepare_header: {url}")
        signature, timestamp = self._generate_signature(url, method, params)

        headers = {
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
        print(f"Request Headers:\n{headers}")
        return headers

    def make_request(self, method, endpoint, params=None, data=None):
        """
        Make a request to the Walmart API.

        Args:
            method (str): HTTP method (e.g., "GET", "POST").
            endpoint (str): API endpoint (e.g., "orders").
            params (dict): Query parameters.
            data (dict): JSON payload.

        Returns:
            dict: Parsed JSON response from the API.
        """
        # Construct the full URL
        url = f"{self.BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        print(f"Request URL: {url}")

        if params:
            query_string = urlencode(params)
            print(f"Query String: {query_string}")
            if "?" in url:
                url = f"{url}&{query_string}"
            else:
                url = f"{url}?{query_string}"
            
            # url = '"'+url+'"'  # Enclose URL in quotes
            print(f"URL with Params in quotes: {url}")


        # Prepare headers
        headers = self._prepare_headers(url, method)
        # print(f"Request Headers: from make_request\n{headers}")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {e}")
