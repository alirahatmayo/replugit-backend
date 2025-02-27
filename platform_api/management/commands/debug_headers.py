from django.core.management.base import BaseCommand
from platform_api.walmart_ca.api_client import WalmartCanadaAPIClient
from platform_api.walmart_ca.orders import WalmartOrders


class Command(BaseCommand):
    help = "Debug Walmart API headers and parameters for manual testing"

    def add_arguments(self, parser):
        parser.add_argument("--created_start_date", type=str, help="Start date for order creation in ISO 8601 format.")
        parser.add_argument("--created_end_date", type=str, help="End date for order creation in ISO 8601 format.")
        parser.add_argument("--ship_start_date", type=str, help="Start date for shipment in ISO 8601 format.")
        parser.add_argument("--ship_end_date", type=str, help="End date for shipment in ISO 8601 format.")
        parser.add_argument("--order_id", type=str, help="Specific order ID to fetch.")

    def handle(self, *args, **kwargs):
        client_id = "a3a150bd-ccd5-43b9-a38c-b2814c1b1b7c"
        private_key = "MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAI6RCEOVvXQpG9s906h8lydVSK73DeR6Agq772RqKBZ/FcZad5RnMvLjcT7gRRWayC5yhsfpEg9Ro15b/5LjWaHECV40A0ebqQdiykmcCfIdarUyHJOwKE7nR3jf5NebVBETyjI2GK4j3lq2ZkuTo5Tm6s11Bxn0cseL5Qjj0mhlAgMBAAECgYB3zJm0KT0VQoIc/lxAxclCjSDRndr3tirHGFu29pmPJeWHU3gOpZWjksoTuuNynyk+FpD5pfm+E60DWq1tokwrKO6/B8HIZ8QDMORyVa4wPxwJ1rFlaCqILQRPKrGNlfHkAstvafnoBjP5f4mmNqwDTTdet4zRglAxpvwfml7ZtQJBAMKmaubDR2yznaFmoRSubXxLFov4zsUvFtTUDCenQGZrxPoeNpzh6+ECkOcjm5Kqm1dB1YT/S5kM9cEwUQTxIdsCQQC7gDCeTYqKSDHQtmuBt2RrEaRMV7rs73u/aDKVwRxR8KRAiUVqXBde8L7PC8VQ3bTkTWDoIoCdOPYRd5Ue1lK/AkEApQYGF8JzaXsWJuIlqqz+8aOPZ/f3BUGY77Me4vdvJ+YyR4MZ9gOrwUY1p2CO4td1f5K2/VybsRRFvhXCepgchQJBAJvhjgn940DllmyzTBuSsSyGhTZm9WPIEfRmly+DVZ0V2ChDN2+eUlu/AJM3cPqy55Gqdvdmv9B2K7UH2vTBMBcCQBVLFO95X5Ic5SgqUGayExZ1sG9YcrCleHKqw/UyQhxVzCpOhVcvFauRUn5mxChvUQ7SL0RxT24p460gijb3VX0="
        channel_type = "d62e611e-606e-41b9-96cf-38ee37331c47"
        
        created_start_date = kwargs.get("created_start_date")
        created_end_date = kwargs.get("created_end_date")
        ship_start_date = kwargs.get("ship_start_date")
        ship_end_date = kwargs.get("ship_end_date")
        order_id = kwargs.get("order_id")

        client = WalmartCanadaAPIClient(client_id, private_key, channel_type)
        orders = WalmartOrders(client)

        try:
            self.stdout.write("Generating request details for debugging...")

            # Build headers and parameters
            endpoint = "orders"
            params = {
                "createdStartDate": created_start_date,
                "createdEndDate": created_end_date,
                "shipStartDate": ship_start_date,
                "shipEndDate": ship_end_date,
                "orderId": order_id,
            }
            params = {k: v for k, v in params.items() if v}

            headers = client._prepare_headers(f"{client.BASE_URL}{endpoint}", "GET")

            # Output headers and parameters
            self.stdout.write("Request Headers:")
            for k, v in headers.items():
                self.stdout.write(f"  {k}: {v}")

            self.stdout.write("Query Parameters:")
            for k, v in params.items():
                self.stdout.write(f"  {k}: {v}")

            # Construct curl command
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{client.BASE_URL}{endpoint}?{query_string}"

            curl_command = f'curl -X GET "{url}" ' + " ".join(
                [f'-H "{k}: {v}"' for k, v in headers.items()]
            )
            self.stdout.write("\nGenerated cURL Command:")
            self.stdout.write(curl_command)

        except Exception as e:
            self.stderr.write(f"Error during debugging: {str(e)}")
