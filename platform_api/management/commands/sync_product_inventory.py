from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Product
from inventory.models import Inventory, Location, InventoryHistory
import json
import time
from decimal import Decimal

# Remove tqdm dependency
# from tqdm import tqdm

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, timezone.datetime):
            return obj.isoformat()
        return super().default(obj)

class Command(BaseCommand):
    help = "Sync inventory for all products in database"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, default="walmart_ca", help="Platform identifier")
        parser.add_argument("--batch-size", type=int, default=10, help="Number of products to process in each batch")
        parser.add_argument("--sleep", type=int, default=2, help="Sleep time between API calls in seconds")
        parser.add_argument("--filter-sku", type=str, help="Filter products by SKU (contains)")
        parser.add_argument("--limit", type=int, help="Limit the number of products to process")
        parser.add_argument("--dry-run", action="store_true", help="Don't update database, just show what would happen")
        parser.add_argument("--output", type=str, help="Output file for results")
        parser.add_argument("--update-db", action="store_true", help="Update database with inventory data")
        parser.add_argument("--only-missing", action="store_true", 
                            help="Only sync products that don't have inventory records")
        
    def handle(self, *args, **options):
        platform_key = options.get("platform")
        batch_size = options.get("batch_size")
        sleep_time = options.get("sleep")
        filter_sku = options.get("filter_sku")
        limit = options.get("limit")
        dry_run = options.get("dry_run")
        update_db = options.get("update_db")
        only_missing = options.get("only_missing")
        
        # Initialize platform API
        if platform_key == "walmart_ca":
            from platform_api.platforms.walmart_ca import WalmartCA
            platform = WalmartCA()
        else:
            self.stderr.write(self.style.ERROR(f"Unknown platform: {platform_key}"))
            return
            
        # Get all products
        products_query = Product.objects.all()
        
        # Apply filters if specified
        if filter_sku:
            products_query = products_query.filter(sku__icontains=filter_sku)
            
        if only_missing:
            # Only get products without inventory records for the platform
            products_query = products_query.filter(inventory_records__isnull=True) | \
                            products_query.exclude(
                                inventory_records__platform=platform_key
                            )
            
        # Apply limit if specified
        if limit:
            products_query = products_query[:limit]
            
        products = list(products_query)
        total_products = len(products)
        
        self.stdout.write(f"Found {total_products} products to process")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No database changes will be made"))
            
        # Process products in batches
        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "items": [],
            "start_time": timezone.now(),
            "end_time": None
        }
        
        batch_count = (total_products + batch_size - 1) // batch_size  # Ceiling division
        
        # Simple progress tracking (without tqdm)
        progress_count = 0
        self.stdout.write(self.style.SUCCESS("Starting inventory sync..."))
        
        for batch_index in range(batch_count):
            start_idx = batch_index * batch_size
            end_idx = min((batch_index + 1) * batch_size, total_products)
            
            batch_products = products[start_idx:end_idx]
            
            # Process each product in the batch
            for product in batch_products:
                sku = product.sku
                progress_count += 1
                
                # Print progress every few items
                if progress_count % 5 == 0 or progress_count == 1 or progress_count == total_products:
                    self.stdout.write(f"Progress: {progress_count}/{total_products} products ({(progress_count/total_products)*100:.1f}%)")
                
                # Get inventory data
                try:
                    self.stdout.write(f"Getting inventory for {sku}")
                    inventory_data = platform.inventory.get_inventory_status(sku)
                    
                    # Record result
                    item_result = {
                        "sku": sku,
                        "success": inventory_data.get("success", False),
                        "status": inventory_data.get("status"),
                        "quantity": inventory_data.get("quantity"),
                        "timestamp": timezone.now()
                    }
                    
                    if inventory_data.get("success"):
                        results["success"] += 1
                        
                        # Update database if requested
                        if update_db and not dry_run:
                            self._update_inventory(platform_key, product, inventory_data)
                    else:
                        results["failed"] += 1
                        item_result["error"] = inventory_data.get("message", "Unknown error")
                        
                    results["items"].append(item_result)
                except Exception as e:
                    results["failed"] += 1
                    results["items"].append({
                        "sku": sku,
                        "success": False,
                        "error": str(e),
                        "timestamp": timezone.now()
                    })
                    self.stderr.write(self.style.ERROR(f"Error processing {sku}: {str(e)}"))
                
            # Sleep between batches to avoid API rate limits
            if batch_index < batch_count - 1:  # Don't sleep after the last batch
                time.sleep(sleep_time)
                
        # Update end time
        results["end_time"] = timezone.now()
        duration = (results["end_time"] - results["start_time"]).total_seconds()
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"Inventory sync completed in {duration:.1f} seconds\n"
            f"Success: {results['success']}, Failed: {results['failed']}, Skipped: {results['skipped']}"
        ))
        
        # Output results to file if requested
        if options.get('output'):
            try:
                with open(options.get('output'), 'w') as f:
                    json.dump(results, f, indent=2, cls=DecimalEncoder)
                self.stdout.write(self.style.SUCCESS(f"Results saved to {options.get('output')}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error saving results: {str(e)}"))
                
    def _update_inventory(self, platform, product, inventory_data):
        """Update inventory in database"""
        try:
            # Get or create location for platform
            location, _ = Location.objects.get_or_create(
                code=platform.upper(),
                defaults={'name': platform.title()}
            )
            
            # Get or create inventory record
            inventory, created = Inventory.objects.get_or_create(
                product=product,
                platform=platform,
                location=location,
                defaults={
                    'quantity': 0,
                    'available_quantity': 0,
                    'reserved_quantity': 0
                }
            )
            
            # Only update if quantity has changed
            quantity = inventory_data.get('quantity', 0)
            
            if inventory.quantity != quantity:
                previous_quantity = inventory.quantity
                
                # Update inventory
                inventory.quantity = quantity
                inventory.available_quantity = quantity  # Simple approach
                
                # Update status based on quantity (model save method will handle this)
                inventory.save()
                
                # Create history record
                InventoryHistory.objects.create(
                    inventory=inventory,
                    previous_quantity=previous_quantity,
                    new_quantity=quantity,
                    change=quantity - previous_quantity,
                    reason='SYNC',
                    reference='Bulk Sync',
                    notes='Updated from platform via sync_product_inventory command'
                )
                
                return True
            return False
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error updating database: {str(e)}"))
            return False

"""
Sync inventory for all products in database

Usage:
    python manage.py sync_product_inventory --platform walmart_ca --update-db

Options:
    --platform PLATFORM       Platform identifier (default: walmart_ca)
    --batch-size SIZE         Number of products to process in each batch (default: 10)
    --sleep SECONDS           Sleep time between API calls in seconds (default: 2)
    --filter-sku PATTERN      Filter products by SKU (contains)
    --limit N                 Limit the number of products to process
    --dry-run                 Don't update database, just show what would happen
    --output FILE             Output file for results
    --update-db               Update database with inventory data
    --only-missing            Only sync products that don't have inventory records

Examples:
    # Basic usage - sync all products
    python manage.py sync_product_inventory --update-db

    # Sync with specific platform
    python manage.py sync_product_inventory --platform walmart_ca --update-db

    # Sync products with smaller batch size and longer sleep time
    python manage.py sync_product_inventory --batch-size 5 --sleep 5 --update-db

    # Sync only products that match a specific SKU pattern
    python manage.py sync_product_inventory --filter-sku "Dell" --update-db

    # Sync only products without inventory records
    python manage.py sync_product_inventory --only-missing --update-db

    # Test run without updating database
    python manage.py sync_product_inventory --dry-run

    # Save results to a file
    python manage.py sync_product_inventory --update-db --output sync-results.json
"""