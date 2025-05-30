from django.core.management.base import BaseCommand, CommandError
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Union
from decimal import Decimal

logger = logging.getLogger(__name__)

# Custom JSON encoder for Decimal values
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class Command(BaseCommand):
    help = "Fetch and manage products from marketplace platforms"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, required=True, help="Platform identifier (e.g., walmart_ca)")
        
        # Operation type
        parser.add_argument("--operation", type=str, default="fetch", 
                           choices=['fetch', 'fetch-all', 'inventory', 'price'],
                           help="Operation to perform")
        
        # Product filters
        parser.add_argument("--sku", type=str, help="Specific product SKU to fetch")
        parser.add_argument("--status", choices=['ACTIVE', 'ARCHIVED', 'RETIRED'], 
                           help="Filter by lifecycle status")
        parser.add_argument("--published", choices=['PUBLISHED', 'UNPUBLISHED'],
                           help="Filter by published status")
        parser.add_argument("--variant-group", type=str, help="Get products by variant group ID")
        
        # Pagination options
        parser.add_argument("--all-pages", action="store_true", help="Fetch all pages of products")
        parser.add_argument("--limit", type=int, default=20, help="Number of products to fetch")
        parser.add_argument("--offset", type=int, help="Offset for pagination")
        
        # Output options
        parser.add_argument("--output-file", type=str, help="Output file for fetched products")
        parser.add_argument("--data-file", type=str, help="JSON file with product data for updates")
        parser.add_argument("--dry-run", action="store_true", help="Process but don't save to database")
        
        # Inventory specific
        parser.add_argument("--quantity", type=int, help="Quantity for inventory update")
        
        # Price specific
        parser.add_argument("--price", type=float, help="Regular price for price update")
        parser.add_argument("--sale-price", type=float, help="Sale price for price update")
        
    def handle(self, *args, **options):
        platform_key = options.get("platform")
        operation = options.get("operation")
        
        # Initialize platform API
        from platform_api.platforms.walmart_ca import WalmartCA
        platform_api = WalmartCA()
        
        # Prepare parameters for API calls
        params = self._build_params_from_options(options)
        
        self.stdout.write(f"Operation: {operation}")
        
        # Execute appropriate operation
        if operation == 'fetch':
            products = platform_api.products.get_products(**params)
            self._handle_products_result(products, options)
            
        elif operation == 'fetch-all':
            self.stdout.write("Fetching all products (this may take a while)...")
            products = platform_api.products.get_all_products(**params)
            self._handle_products_result(products, options)
            
        elif operation == 'inventory':
            self._update_inventory(platform_api, options)
            
        elif operation == 'price':
            self._update_price(platform_api, options)
    
    def _build_params_from_options(self, options):
        """Build API parameters from command options"""
        params = {
            'limit': options.get('limit'),
            'dry_run': options.get('dry_run', False)
        }
        
        # Add filters if provided
        if options.get('sku'):
            params['sku'] = options.get('sku')
            
        if options.get('offset') is not None:
            params['offset'] = options.get('offset')
            
        if options.get('status'):
            params['lifecycleStatus'] = options.get('status')
            
        if options.get('published'):
            params['publishedStatus'] = options.get('published')
            
        if options.get('variant_group'):
            params['variantGroupId'] = options.get('variant_group')
            
        return params
    
    def _handle_products_result(self, products, options):
        """Handle the products result"""
        if not products:
            self.stdout.write("No products found")
            return
            
        self.stdout.write(f"Found {len(products)} products")
        
        if options.get('output_file'):
            with open(options.get('output_file'), 'w') as f:
                json.dump(products, f, indent=2, cls=DecimalEncoder)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {options.get('output_file')}"))
        else:
            # Print first 5 products
            if len(products) > 5:
                self.stdout.write(json.dumps(products[:5], indent=2, cls=DecimalEncoder))
                self.stdout.write(f"... and {len(products) - 5} more products")
            else:
                self.stdout.write(json.dumps(products, indent=2, cls=DecimalEncoder))
    
    def _update_inventory(self, platform_api, options):
        """Update inventory levels"""
        items = []
        
        if options.get('data_file'):
            try:
                with open(options.get('data_file'), 'r') as f:
                    items = json.load(f)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error reading data file: {str(e)}"))
                return
        elif options.get('sku') and options.get('quantity') is not None:
            items = [{
                "sku": options.get('sku'),
                "quantity": options.get('quantity')
            }]
        else:
            self.stderr.write(self.style.ERROR("Either --data-file or --sku and --quantity are required"))
            return
            
        self.stdout.write(f"Updating inventory for {len(items)} products...")
        
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING("DRY RUN: No actual updates will be made"))
            self.stdout.write(json.dumps(items, indent=2))
            return
            
        response = platform_api.products.update_inventory(items)
        self.stdout.write(self.style.SUCCESS(f"Updated inventory for {len(items)} products"))
        self.stdout.write(json.dumps(response, indent=2, cls=DecimalEncoder))
    
    def _update_price(self, platform_api, options):
        """Update product prices"""
        items = []
        
        if options.get('data_file'):
            try:
                with open(options.get('data_file'), 'r') as f:
                    items = json.load(f)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error reading data file: {str(e)}"))
                return
        elif options.get('sku') and options.get('price') is not None:
            item = {
                "sku": options.get('sku'),
                "price": options.get('price')
            }
            if options.get('sale_price') is not None:
                item["sale_price"] = options.get('sale_price')
                
            items = [item]
        else:
            self.stderr.write(self.style.ERROR("Either --data-file or --sku and --price are required"))
            return
            
        self.stdout.write(f"Updating prices for {len(items)} products...")
        
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING("DRY RUN: No actual updates will be made"))
            self.stdout.write(json.dumps(items, indent=2))
            return
            
        response = platform_api.products.update_price(items)
        self.stdout.write(self.style.SUCCESS(f"Updated prices for {len(items)} products"))
        self.stdout.write(json.dumps(response, indent=2, cls=DecimalEncoder))

"""
Available commands for Walmart CA product operations:

# Basic product operations:
# -----------------------

# Fetch a single product by SKU
python manage.py fetch_products --platform walmart_ca --operation fetch --sku "Len-T490-16-512"

# Fetch multiple products (up to the limit)
python manage.py fetch_products --platform walmart_ca --operation fetch --limit 50

# Fetch all products (paginated)
python manage.py fetch_products --platform walmart_ca --operation fetch-all

# Save fetch results to file
python manage.py fetch_products --platform walmart_ca --operation fetch-all --output-file products.json

# Product filtering options:
# ------------------------

# Filter by lifecycle status
python manage.py fetch_products --platform walmart_ca --operation fetch-all --status ACTIVE

# Filter by published status
python manage.py fetch_products --platform walmart_ca --operation fetch-all --published PUBLISHED

# Filter by variant group
python manage.py fetch_products --platform walmart_ca --operation fetch-all --variant-group "ABC123"

# Combined filters
python manage.py fetch_products --platform walmart_ca --operation fetch-all --status ACTIVE --published PUBLISHED

# Pagination
python manage.py fetch_products --platform walmart_ca --operation fetch --limit 20 --offset 60

# Inventory operations:
# ------------------

# Update inventory for a single product
python manage.py fetch_products --platform walmart_ca --operation inventory --sku "Len-T490-16-512" --quantity 10

# Test inventory update without making API calls
python manage.py fetch_products --platform walmart_ca --operation inventory --sku "Len-T490-16-512" --quantity 10 --dry-run

# Bulk inventory update from JSON file (format: [{"sku": "SKU1", "quantity": 5}, {"sku": "SKU2", "quantity": 10}])
python manage.py fetch_products --platform walmart_ca --operation inventory --data-file inventory.json

# Price operations:
# ----------------

# Update regular price for a product
python manage.py fetch_products --platform walmart_ca --operation price --sku "Len-T490-16-512" --price 499.99

# Update regular price and sale price
python manage.py fetch_products --platform walmart_ca --operation price --sku "Len-T490-16-512" --price 499.99 --sale-price 449.99

# Test price update without making API calls
python manage.py fetch_products --platform walmart_ca --operation price --sku "Len-T490-16-512" --price 499.99 --dry-run

# Bulk price update from JSON file (format: [{"sku": "SKU1", "price": 49.99, "sale_price": 39.99}, {"sku": "SKU2", "price": 99.99}])
python manage.py fetch_products --platform walmart_ca --operation price --data-file prices.json
"""