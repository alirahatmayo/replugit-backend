# platform_api/management/commands/fetch_products_ca.py

from django.core.management.base import BaseCommand
from platform_api.walmart_ca.api_client import WalmartCanadaAPIClient
from platform_api.walmart_ca.products import WalmartProducts
from products.models import Product
# from utils.walmart_ca_utils import map_to_schema
from .utils.walmart_ca_utils import map_to_schema
import logging
import json
from pathlib import Path
from datetime import datetime
from django.db.models import Q
from django.conf import settings

# Define the map_to_schema function

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch products from Walmart Canada API and perform actions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            choices=["fetch_products", "fetch_by_sku"],
            default="fetch_products",
            help="Action to perform."
        )
        parser.add_argument("--limit", type=int, default=50, help="Number of products per request.")
        parser.add_argument("--offset", type=int, default=0, help="Pagination offset.")
        parser.add_argument("--sku", type=str, help="Fetch a specific product by SKU.")
        parser.add_argument("--dry-run", action="store_true", help="Print product data without saving it.")
        parser.add_argument("--save-response", action="store_true", help="Save API responses to file.")
        parser.add_argument(
            "--include-details",
            type=bool,
            default=True,
            help="Include detailed product information in the response."
        )

    def handle(self, *args, **kwargs):
        private_key = settings.WALMART_CA_CLIENT_SECRET
        client_id = settings.WALMART_CA_CLIENT_ID
        channel_type = settings.WALMART_CA_CHANNEL_TYPE

        client = WalmartCanadaAPIClient(client_id, private_key, channel_type)
        products_api = WalmartProducts(client)

        action = kwargs.get("action")
        limit = kwargs.get("limit")
        offset = kwargs.get("offset")
        sku = kwargs.get("sku")
        dry_run = kwargs.get("dry_run")
        save_response = kwargs.get("save_response")
        include_details = kwargs.get("include_details")

        if action == "fetch_by_sku":
            if not sku:
                self.stderr.write("SKU is required for fetch_by_sku action.")
                return
            self.fetch_by_sku(products_api, sku, dry_run, save_response)
        elif action == "fetch_products":
            self.fetch_products(products_api, limit, offset, dry_run, save_response, include_details)
        else:
            self.stderr.write(f"Unknown action: {action}")

    def fetch_by_sku(self, products_api, sku, dry_run, save_response):
        """
        Fetch a specific product by SKU from the Walmart Canada API.

        Args:
            products_api (WalmartProducts): The WalmartProducts API client.
            sku (str): The SKU of the product to fetch.
            dry_run (bool): If True, print product data without saving it.
            save_response (bool): If True, save the API response to a file.
        """
        self.stdout.write(f"Fetching product details for SKU: {sku}")
        
        try:
            # Fetch the product data using the API
            print(f"sku from fetch by sku 1st: {sku}")
            response = products_api.fetch_product_by_sku(sku)
            item_data = response.get("ItemResponse", [])

            # Ensure item_data is not empty
            if not item_data:
                raise ValueError(f"No data found for SKU: {sku}")

            # Extract SKU if it's missing
            sku = sku or item_data[0].get("sku")
            print(f"sku from fetch by sku: {sku}")
            print(f"item_data from fetch by sku: {item_data}")

            # Handle dry run and save response options
            if dry_run:
                self.stdout.write(f"Dry Run: {item_data}")
            if save_response:
                self.save_response_to_file(item_data, sku)
            else:
                self.save_product(item_data[0])  # Pass the first item's data to save_product
        except Exception as e:
            self.stderr.write(f"Error fetching product by SKU: {e}")

    def fetch_products(self, products_api, limit, offset, dry_run, save_response, include_details):
        try:
            while True:
                response = products_api.fetch_products(include_details=include_details, limit=limit, offset=offset)
                items = response.get("ItemResponse", [{}])
                if save_response:
                    self.save_response_to_file(response, f"offset_{offset}")

                if not items:
                    self.stdout.write("No more products to fetch.")
                    break

                for item_data in items:
                    if dry_run:
                        self.stdout.write(f"Dry Run: {item_data}")
                    else:
                        try:
                            self.save_product(item_data)
                        except Exception as e:
                            logger.error(f"Error saving product {item_data.get('sku')}: {e}")
                            continue

                offset += len(items)
                if len(items) < limit:
                    break
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            self.stderr.write(f"Error: {e}")

    def save_product(self, item_data, platform_name="walmart_ca"):
        """
        Save or update a product using the API response data.

        Args:
            item_data (dict): The product data from the API response.
            platform_name (str): The name of the platform providing the data (e.g., "walmart_ca").
        """
        if not item_data:
            logger.error("Empty or invalid item_data provided.")
            return

        try:
            platform_name = platform_name.lower()
            sku = item_data.get("sku")
            print (f"from the sku sku: {sku}")
            gtin = item_data.get("gtin")

            # Validate essential fields
            if not sku and not gtin:
                raise ValueError("Both SKU and GTIN are missing. Cannot identify the product.")

            # Fetch existing product based on SKU and GTIN
            query = Q()
            if sku:
                query |= Q(sku=sku)
            if gtin:
                query |= Q(gtin=gtin)
            existing_products = Product.objects.filter(query)

            if existing_products.count() > 1:
                raise ValueError(f"Multiple products found with SKU: {sku} or GTIN: {gtin}. Please ensure unique identifiers.")
            existing_product = existing_products.first()

            # Map data to schema
            platform_data = existing_product.platform_data if existing_product else {}
            platform_data[platform_name] = map_to_schema(item_data)

            # Save or update the product
            product, created = Product.objects.update_or_create(
                sku=sku,
                gtin=gtin,
                defaults={
                    "name": item_data.get("productName", ""),
                    "platform": platform_name,
                    "product_type": item_data.get("productType", "UNKNOWN"),
                    "platform_data": platform_data,
                },
            )

            logger.info(f"{'Created' if created else 'Updated'} product: {product.name} (SKU: {sku}, GTIN: {gtin}) on {platform_name}")
        except Exception as e:
            logger.error(f"Error saving product (SKU: {sku}, GTIN: {gtin}) on {platform_name}: {e}")
            raise



    def save_response_to_file(self, response, identifier):
        """
        Save the API response to a text file for reference.

        Args:
            response (dict): The API response data.
            identifier (str): A unique identifier for the file name (e.g., SKU or offset).
        """
        output_dir = Path("walmart_responses")
        output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir / f"{identifier}_response.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=4)

        logger.info(f"Saved API response to {file_path}")



# python manage.py fetch_products_ca --action=fetch_products --include-details=true --limit=20 --offset=0
# python manage.py fetch_products_ca --action=fetch_products --include-details=false
# python manage.py fetch_products_ca --include-details=true --limit=50 --offset=0 --save-response
# python manage.py fetch_products_ca --action="fetch_by_sku" --sku=Len-T490-16-1000-i7
