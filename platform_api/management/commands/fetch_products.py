from django.core.management.base import BaseCommand, CommandError
from platform_api.processors.registry.product import ProductProcessorRegistry
from platform_api.registry import PlatformRegistry
import logging
import json
import csv
from pathlib import Path
from .utils.walmart_ca_utils import map_to_schema
from typing import Dict, Any, Tuple, Union

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Fetch products from a specified platform and process them via the new architecture"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, required=True,
                            help="Platform identifier (e.g., walmart_ca, amazon_us, shopify)")
        parser.add_argument("--action", type=str, choices=["fetch_all", "fetch_by_sku"],
                            default="fetch_all", help="Action to perform")
        parser.add_argument("--limit", type=int, default=50,
                            help="Number of products per request")
        parser.add_argument("--offset", type=int, default=0,
                            help="Pagination offset")
        parser.add_argument("--sku", type=str, help="Fetch specific product by SKU")
        parser.add_argument("--output", type=str, choices=['console', 'json', 'csv'],
                            default='console', help="Output format for fetched products")
        parser.add_argument("--output-file", type=str,
                            help="Output file path (for JSON/CSV output)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be processed without making changes")
        parser.add_argument("--save-response", action="store_true",
                            help="Save API responses to file")
        parser.add_argument("--extra_options", type=str,
                            help="Extra JSON parameters for platform-specific options (e.g., '{\"category\": \"electronics\", \"brand\": \"sony\"}')")

    def handle(self, *args, **options):
        platform_key = options.get("platform")
        if not platform_key:
            raise CommandError("Platform parameter is required")
        try:
            # Get platform and processor from our registries/abstractions.
            platform = PlatformRegistry.get_platform(platform_key)
            processor = ProductProcessorRegistry.get_processor(platform_key)
            action = options["action"]
            if action == "fetch_by_sku":
                self._handle_fetch_by_sku(platform, processor, options)
            else:
                self._handle_fetch_all(platform, processor, options)
        except Exception as e:
            logger.error(f"Unexpected error in fetch_products command: {e}", exc_info=True)
            raise CommandError(f"Unexpected error: {e}")

    def _process_single_product(self, product_data: Dict[str, Any], processor, options) -> Tuple[Dict[str, Any], bool]:
        """Process a single product and return its processed data."""
        try:
            mapped_data = map_to_schema(product_data)
            if options.get("dry_run"):
                return mapped_data, True
            
            product = processor.process_product(mapped_data)
            # Get the processed data directly from the platform_data
            processed_data = product.platform_data.get(product.platform, {})
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Processed [{product.sku}] - {product.name[:50]}..."))
            return processed_data, True
        except Exception as e:
            sku = product_data.get('sku', 'Unknown SKU')
            error_msg = f"Error processing [{sku}]: {str(e)}"
            self.stdout.write(self.style.ERROR(f"✗ {error_msg}"))
            return {'sku': sku, 'error': error_msg}, False


    def _handle_fetch_by_sku(self, platform, processor, options):
        """Handle fetching a single product by SKU"""
        sku = options.get("sku")
        if not sku:
            raise CommandError("SKU is required for fetch_by_sku action")
        
        self.stdout.write(f"Fetching product with SKU: {sku}")
        try:
            product_data = platform.fetch_product_by_sku(sku)
            summary, success = self._process_single_product(product_data, processor, options)
            
            if options.get("dry_run"):
                self.stdout.write(self.style.SUCCESS(f"Dry run; would process: {summary}"))
                return
            
            if success:
                self._handle_output([summary], [], options)
            else:
                self._handle_output([], [summary], options)
                
        except Exception as e:
            logger.error(f"Error processing product {sku}: {e}")
            self.stderr.write(self.style.ERROR(f"Error: {e}"))

    def _handle_fetch_all(self, platform, processor, options):
        """Handle fetching all products with pagination"""
        limit = options["limit"]
        offset = options["offset"]
        processed = []
        errors = []
        
        self.stdout.write(f"Fetching products from offset: {offset}")
        
        try:
            if options.get("dry_run"):
                self.stdout.write(self.style.SUCCESS("Dry run: Would process products"))
                return
                
            while True:
                self.stdout.write(self.style.WARNING("\nMaking API request..."))
                products = platform.fetch_products(limit=limit, offset=offset)
                
                if not products:
                    self.stdout.write(self.style.WARNING("No products returned from API"))
                    break
                    
                self.stdout.write(f"\nProcessing batch of {len(products)} products...")
                
                for product_data in products:
                    summary, success = self._process_single_product(product_data, processor, options)
                    if success:
                        processed.append(summary)
                    else:
                        errors.append(summary)
                
                offset += len(products)
                if len(products) < limit:
                    break
                    
            self._print_processing_summary(len(processed), len(errors))
            self._handle_output(processed, errors, options)
            
        except Exception as e:
            logger.error(f"Error fetching products: {e}", exc_info=True)
            raise CommandError(str(e))

    def _print_processing_summary(self, total_processed: int, total_errors: int):
        """Print a summary of the processing results."""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Processing complete:")
        self.stdout.write(f"✓ Successfully processed: {total_processed}")
        self.stdout.write(f"✗ Errors: {total_errors}")
        self.stdout.write("=" * 50)

    def _build_params(self, options):
        """Build parameters dictionary with validation"""
        params = {
            "limit": options.get("limit", 50),
            "offset": options.get("offset", 0)
        }
        if category := options.get("category"):
            params["category"] = category
        if extra_options := options.get("extra_options"):
            try:
                extra = json.loads(extra_options)
                params.update(extra)
            except json.JSONDecodeError:
                raise CommandError("Invalid JSON in extra_options")
        return params

    def _handle_output(self, processed, errors, options):
        """Handle command output based on specified format"""
        output_format = options.get('output', 'console')
        output_file = options.get('output_file')
        
        self.stdout.write("\nProcessing Summary:")
        self.stdout.write(f"Successfully processed: {len(processed)}")
        self.stdout.write(f"Failed: {len(errors)}")

        if output_format in ['json', 'csv'] and not output_file:
            raise CommandError("Output file is required for JSON/CSV output")

        if output_format == 'console':
            return
            
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_format == 'json':
            with output_path.open('w', encoding='utf-8') as f:
                json.dump({'products': processed, 'errors': errors}, f, indent=2)
        elif output_format == 'csv':
            with output_path.open('w', newline='', encoding='utf-8') as f:
                # Get fieldnames from the first product's keys
                fieldnames = list(processed[0].keys()) if processed else []
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(processed)


#----Commands----
# python manage.py fetch_products --platform=walmart_ca --action=fetch_all --limit=50 --offset=0 --output=console
# python manage.py fetch_products --platform=walmart_ca --action=fetch_all --limit=50 --offset=0 --output=json --output-file=products.json
# python manage.py fetch_products --platform=walmart_ca --action=fetch_all --limit=50 --offset=0 --output=csv --output-file=products.csv
# python manage.py fetch_products --platform=walmart_ca --action=fetch_by_sku --sku=A15-128-BLK-WM
# python manage.py fetch_products --platform=walmart_ca --action=fetch_by_sku --sku=A15-128-BLK-WM --dry-run
# python manage.py fetch_products --platform=walmart_ca --action=fetch_by_sku --sku=A15-128-BLK-WM --dry-run --save-response
# python manage.py fetch_products --platform=walmart_ca --action=fetch_by_sku --sku=A15-128-BLK-WM --dry-run --save-response --output=console
# python manage.py fetch_products --platform=walmart_ca --action=fetch_by_sku --sku=A15-128-BLK-WM --dry-run --save-response --output=json --output-file=product.json