from django.core.management.base import BaseCommand
import json
from decimal import Decimal
from django.utils import timezone

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class Command(BaseCommand):
    help = "Manage inventory for marketplace platforms"

    """
    Examples:

    # Update inventory for a specific SKU with quantity 10 and lag time 1 day
    python manage.py manage_inventory --platform walmart_ca --action update --sku "ABC123" --quantity 10 --lag-time 1

    # Bulk update from JSON file
    python manage.py manage_inventory --platform walmart_ca --action update --data-file inventory.json

    # JSON file format example:
    # [
    #   {"sku": "ABC123", "quantity": 10, "lag_time": 1},
    #   {"sku": "XYZ456", "quantity": 5, "lag_time": 2}
    # ]

    # Get current inventory for a SKU
    python manage.py manage_inventory --platform walmart_ca --action status --sku "ABC123"
    """

    """
    Walmart CA Inventory Management Commands

    Available commands for inventory operations:

    # Status Operations:
    # -----------------

    # Get inventory status for a specific SKU
    python manage.py manage_inventory --action status --sku "Dell-5490-16-256-i7"

    # Get inventory status and save to file
    python manage.py manage_inventory --action status --sku "Dell-5490-16-256-i7" --output inventory-status.json

    # Find all items with low stock (default threshold is 5)
    python manage.py manage_inventory --action low-stock

    # Find items with critical stock levels (threshold of 2)
    python manage.py manage_inventory --action low-stock --threshold 2

    # Update Operations:
    # ----------------

    # Update inventory quantity for a single item (with default 1-day lag time)
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 10

    # Update inventory with specific fulfillment lag time
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 15 --lag-time 2

    # Mark an item as out of stock
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 0

    # Bulk update from JSON file
    python manage.py manage_inventory --action update --data-file inventory-updates.json

    # JSON file format example:
    # [
    #   {"sku": "Dell-5490-16-256-i7", "quantity": 10, "lag_time": 1},
    #   {"sku": "Dell-5400-8-256", "quantity": 5, "lag_time": 2},
    #   {"sku": "Len-T490-16-512", "quantity": 8}
    # ]

    # Sync Operations:
    # --------------

    # Sync inventory for a specific SKU (pulls latest from Walmart CA to local DB)
    python manage.py manage_inventory --action sync --sku "Dell-5490-16-256-i7"

    # Sync inventory for a specific SKU and save results to file
    python manage.py manage_inventory --action sync --sku "Dell-5490-16-256-i7" --output sync-results.json

    # Sync inventory for ALL products (may take a while)
    python manage.py manage_inventory --action sync-all

    # Sync all products and save results to file
    python manage.py manage_inventory --action sync-all --output all-sync-results.json
    """

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, default="walmart_ca", help="Platform identifier")
        parser.add_argument(
            "--action", 
            type=str, 
            required=True,
            choices=['update', 'sync', 'sync-all', 'status', 'low-stock'],
            help="Action to perform"
        )
        parser.add_argument("--sku", type=str, help="Product SKU for specific operations")
        parser.add_argument("--quantity", type=int, help="New quantity for updates")
        parser.add_argument("--lag-time", type=int, default=1, 
                            help="Fulfillment lag time in days (time between order and shipment)")
        parser.add_argument("--threshold", type=int, default=5, help="Threshold for low-stock items")
        parser.add_argument("--data-file", type=str, help="JSON file with inventory data")
        parser.add_argument("--output", type=str, help="Output file for results")
        
    def handle(self, *args, **options):
        platform_key = options.get("platform")
        action = options.get("action")
        
        # Initialize platform API
        from platform_api.platforms.walmart_ca import WalmartCA
        
        platform = WalmartCA()
        
        if action == 'update':
            self._update_inventory(platform, options)
            
        elif action == 'sync':
            self._sync_inventory(platform, options)
            
        elif action == 'sync-all':
            self._sync_all_inventory(platform, options)
            
        elif action == 'status':
            self._get_inventory_status(platform, options)
            
        elif action == 'low-stock':
            self._get_low_stock(platform, options)
            
    def _update_inventory(self, platform, options):
        """Update inventory quantities"""
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
                "quantity": options.get('quantity'),
                "lag_time": options.get('lag_time', 2)  # Include lag time
            }]
        else:
            self.stderr.write(self.style.ERROR("Either --data-file or --sku and --quantity are required"))
            return
            
        self.stdout.write(f"Updating inventory for {len(items)} products...")
        response = platform.inventory.update_inventory(items)
        
        self.stdout.write(self.style.SUCCESS(
            f"Updated inventory: {response.get('success')} successful, {response.get('failed')} failed"
        ))
        self._output_results(response, options)
            
    def _sync_inventory(self, platform, options):
        """Sync inventory for a specific product"""
        sku = options.get('sku')
        
        if not sku:
            self.stderr.write(self.style.ERROR("--sku is required for sync operation"))
            return
            
        self.stdout.write(f"Syncing inventory for {sku}...")
        response = platform.inventory.sync_inventory(sku)
        
        if response.get('success'):
            self.stdout.write(self.style.SUCCESS(f"Synced inventory for {sku}"))
            self.stdout.write(f"Platform quantity: {response.get('platform_quantity')}")
            self.stdout.write(f"Local quantity: {response.get('current_quantity')}")
        else:
            self.stderr.write(self.style.ERROR(f"Error syncing inventory: {response.get('message')}"))
            
        self._output_results(response, options)
            
    def _sync_all_inventory(self, platform, options):
        """Sync inventory for all products"""
        self.stdout.write("Syncing inventory for all products (this may take a while)...")
        
        response = platform.inventory.sync_all_inventory()
        
        self.stdout.write(self.style.SUCCESS(
            f"Sync completed: {response.get('success', 0)} successful, "
            f"{response.get('failed', 0)} failed"
        ))
        
        self._output_results(response, options)
            
    def _get_inventory_status(self, platform, options):
        """Get inventory status for a product"""
        sku = options.get('sku')
        
        if not sku:
            self.stderr.write(self.style.ERROR("--sku is required for status operation"))
            return
            
        self.stdout.write(f"Getting inventory status for {sku}...")
        response = platform.inventory.get_inventory_status(sku)
        
        if response.get('success'):
            self.stdout.write(self.style.SUCCESS(f"Inventory status for {sku}:"))
            self.stdout.write(f"Status: {response.get('status')}")
            self.stdout.write(f"Quantity: {response.get('quantity')}")
            
            # Show local comparison
            if response.get('synced') is not None:
                sync_status = "IN SYNC" if response.get('synced') else "OUT OF SYNC"
                self.stdout.write(f"Local quantity: {response.get('local_quantity')}")
                self.stdout.write(f"Sync status: {sync_status}")
        else:
            self.stderr.write(self.style.ERROR(f"Error getting status: {response.get('message')}"))
            
        self._output_results(response, options)
            
    def _get_low_stock(self, platform, options):
        """Get low stock items"""
        threshold = options.get('threshold', 5)
        
        self.stdout.write(f"Getting items with stock <= {threshold}...")
        response = platform.inventory.get_low_stock_items(threshold=threshold)
        
        if response:
            self.stdout.write(self.style.SUCCESS(f"Found {len(response)} items with low stock"))
            for item in response[:10]:  # Show first 10
                self.stdout.write(f"{item.get('sku')}: {item.get('quantity')} units")
                
            if len(response) > 10:
                self.stdout.write(f"... and {len(response) - 10} more items")
        else:
            self.stdout.write("No low stock items found")
            
        self._output_results(response, options)
            
    def _output_results(self, data, options):
        """Output results to file if requested"""
        if options.get('output'):
            try:
                with open(options.get('output'), 'w') as f:
                    json.dump(data, f, indent=2, cls=DecimalEncoder)
                self.stdout.write(self.style.SUCCESS(f"Results saved to {options.get('output')}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error saving results: {str(e)}"))



    

""" Walmart CA Inventory Management Commands

    Available commands for inventory operations:

    # Status Operations:
    # -----------------

    # Get inventory status for a specific SKU
    python manage.py manage_inventory --action status --sku "Dell-5490-16-256-i7"

    # Get inventory status and save to file
    python manage.py manage_inventory --action status --sku "Dell-5490-16-256-i7" --output inventory-status.json

    # Find all items with low stock (default threshold is 5)
    python manage.py manage_inventory --action low-stock

    # Find items with critical stock levels (threshold of 2)
    python manage.py manage_inventory --action low-stock --threshold 2

    # Update Operations:
    # ----------------

    # Update inventory quantity for a single item (with default 1-day lag time)
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 10

    # Update inventory with specific fulfillment lag time
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 15 --lag-time 2

    # Mark an item as out of stock
    python manage.py manage_inventory --action update --sku "Dell-5490-16-256-i7" --quantity 0

    # Bulk update from JSON file
    python manage.py manage_inventory --action update --data-file inventory-updates.json

    # JSON file format example:
    # [
    #   {"sku": "Dell-5490-16-256-i7", "quantity": 10, "lag_time": 1},
    #   {"sku": "Dell-5400-8-256", "quantity": 5, "lag_time": 2},
    #   {"sku": "Len-T490-16-512", "quantity": 8}
    # ]

    # Sync Operations:
    # --------------

    # Sync inventory for a specific SKU (pulls latest from Walmart CA to local DB)
    python manage.py manage_inventory --action sync --sku "Dell-5490-16-256-i7"

    # Sync inventory for a specific SKU and save results to file
    python manage.py manage_inventory --action sync --sku "Dell-5490-16-256-i7" --output sync-results.json

    # Sync inventory for ALL products (may take a while)
    python manage.py manage_inventory --action sync-all

    # Sync all products and save results to file
    python manage.py manage_inventory --action sync-all --output all-sync-results.json
    """