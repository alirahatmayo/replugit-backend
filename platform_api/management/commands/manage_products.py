from django.core.management.base import BaseCommand
import json

class Command(BaseCommand):
    help = "Manage Walmart CA products (fetch, update inventory, update prices)"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, default="walmart_ca", help="Platform identifier")
        parser.add_argument("--action", type=str, required=True, 
                           choices=['get', 'inventory', 'price'],
                           help="Action to perform")
        parser.add_argument("--sku", type=str, help="Product SKU for specific product")
        parser.add_argument("--data-file", type=str, help="JSON file with product data")
        parser.add_argument("--all", action="store_true", help="Fetch all products with pagination")
        parser.add_argument("--output", type=str, help="Output file for fetched products")
        
        # Inventory specific
        parser.add_argument("--quantity", type=int, help="Quantity for inventory update")
        
        # Price specific
        parser.add_argument("--price", type=float, help="Regular price for price update")
        parser.add_argument("--sale-price", type=float, help="Sale price for price update")
        
    def handle(self, *args, **options):
        from platform_api.platforms.walmart_ca import WalmartCA
        platform = WalmartCA()
        
        action = options.get("action")
        if action == 'get':
            self.fetch_products(platform, options)
        elif action == 'inventory':
            self.update_inventory(platform, options)
        elif action == 'price':
            self.update_price(platform, options)
            
    def fetch_products(self, platform, options):
        """Fetch products from platform"""
        sku = options.get('sku')
        
        if options.get('all'):
            products = platform.products.get_all_products(sku=sku)
        else:
            products = platform.products.get_products(sku=sku)
            
        self.stdout.write(f"Fetched {len(products)} products")
        
        if options.get('output'):
            with open(options.get('output'), 'w') as f:
                json.dump(products, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Saved products to {options.get('output')}"))
        else:
            self.stdout.write(json.dumps(products[:5], indent=2))
            if len(products) > 5:
                self.stdout.write(f"... {len(products)-5} more products not shown")
    
    def update_inventory(self, platform, options):
        """Update inventory levels"""
        items = []
        
        if options.get('data_file'):
            with open(options.get('data_file'), 'r') as f:
                items = json.load(f)
        elif options.get('sku') and options.get('quantity') is not None:
            items = [{
                "sku": options.get('sku'),
                "quantity": options.get('quantity')
            }]
        else:
            self.stderr.write("Either --data-file or --sku and --quantity are required")
            return
            
        response = platform.products.update_inventory(items)
        self.stdout.write(self.style.SUCCESS(f"Updated inventory for {len(items)} products"))
        self.stdout.write(json.dumps(response, indent=2))
        
    def update_price(self, platform, options):
        """Update product prices"""
        items = []
        
        if options.get('data_file'):
            with open(options.get('data_file'), 'r') as f:
                items = json.load(f)
        elif options.get('sku') and options.get('price') is not None:
            item = {
                "sku": options.get('sku'),
                "price": options.get('price')
            }
            if options.get('sale_price') is not None:
                item["sale_price"] = options.get('sale_price')
                
            items = [item]
        else:
            self.stderr.write("Either --data-file or --sku and --price are required")
            return
            
        response = platform.products.update_price(items)
        self.stdout.write(self.style.SUCCESS(f"Updated prices for {len(items)} products"))
        self.stdout.write(json.dumps(response, indent=2))