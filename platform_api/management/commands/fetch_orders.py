from django.core.management.base import BaseCommand, CommandError
import logging
import json
from datetime import datetime
from time import sleep
from decimal import Decimal
from platform_api.registry import PlatformRegistry
from platform_api.platforms.walmart_ca.orders.processor import WalmartCAOrderProcessor

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Fetch orders from a specified platform"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, required=True, help="Platform identifier (e.g., walmart_ca)")
        parser.add_argument("--order-id", type=str, help="Fetch specific order by ID")
        parser.add_argument("--start_date", type=str, help="Start date in ISO format (YYYY-MM-DD)")
        parser.add_argument("--end_date", type=str, help="End date in ISO format (YYYY-MM-DD)")
        parser.add_argument("--extra_options", type=str, help="Extra JSON parameters for platform-specific options")
        parser.add_argument("--status", type=str, choices=['pending', 'shipped', 'cancelled', 'all'], default='all', help="Filter orders by status")
        parser.add_argument("--output", type=str, choices=['console', 'json', 'csv'], default='console', help="Output format")
        parser.add_argument("--output-file", type=str, help="Output file path (for JSON/CSV output)")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without making changes")
        parser.add_argument("--sku", type=str, help="Filter by specific product SKU")
        parser.add_argument("--from-ship-date", type=str, help="Expected ship date from (YYYY-MM-DD)")
        parser.add_argument("--to-ship-date", type=str, help="Expected ship date to (YYYY-MM-DD)")
        parser.add_argument("--product-info", action="store_true", help="Include product information in response")
        parser.add_argument("--all-pages", action="store_true", help="Fetch all pages of results (pagination)")

    def handle(self, *args, **options):
        """Handle command execution"""
        platform_key = options.get("platform")
        if not platform_key:
            raise CommandError("Platform parameter is required")

        order_id = options.get("order_id")
        # Instantiate the processor based on the platform key
        if platform_key.lower() == "walmart_ca":
            processor = WalmartCAOrderProcessor()
            print("Walmart CA processor instantiated")
        else:
            print("Platform not supported")
            processor = PlatformRegistry.get_processor(platform_key)

        try:
            platform_api = PlatformRegistry.get_platform(platform_key)
            
            if order_id:
                # Process a single order
                order_data = platform_api.fetch_orders(order_id=order_id)
                if not order_data:
                    self.stderr.write(f"Order {order_id} not found")
                    return
                    
                # Print raw order data
                self.stdout.write("Raw order data:")
                self.stdout.write(json.dumps(order_data, indent=2))
                
                order = processor.process_order(order_data)
                self.stdout.write(self.style.SUCCESS(
                    f"Processed order {order_id} - Customer: {order.customer}"
                ))
                return

            # Fetch multiple orders
            params = self._build_params(options)
            orders = platform_api.fetch_orders(**params)
            
            if not orders:
                self.stdout.write("No orders found for the given criteria")
                return
                
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(orders)} orders from {platform_key}"))
            
            # Process orders
            for order_data in orders:
                # Debug the actual order ID from the raw data
                order_id = order_data.get('purchaseOrderId', 'Unknown')
                print(f"Processing order: {order_id}")
                
                try:
                    processed_order = processor.process_order(order_data)
                    if not processed_order:
                        self.stderr.write(self.style.ERROR(f"Failed to process order {order_id}: Processor returned None"))
                        continue
                        
                    # Add a debug print to verify we have a proper order object
                    print(f"Processed order object: {processed_order.order_number}, Email: '{processed_order.relay_email}', Phone: '{processed_order.phone_number}'")
                    
                    saved_order = processor.save_order(processed_order)
                    
                    # Format order status change
                    status_msg = ""
                    if hasattr(saved_order, '_status_changed'):
                        status_msg = self.style.WARNING(
                            f" (Status changed from {saved_order._previous_status} "
                            f"to {saved_order.state})"
                        )

                    # Build item summary
                    items_summary = []
                    total_items = 0
                    for item in saved_order.items.all():
                        price_data = item.price_data
                        if isinstance(price_data, dict):
                            # Use the correct structure based on your PriceFormatter output
                            if 'totals' in price_data and 'grand_total' in price_data['totals']:
                                # New price data format
                                price = Decimal(price_data['totals']['grand_total'])
                                currency = price_data['totals']['currency']
                            else:
                                # Fallback to old format
                                price = Decimal(price_data.get('amount', '0.00'))
                                currency = price_data.get('currency', 'CAD')
                                
                            items_summary.append(
                                f"\n    - {item.quantity}x {item.product.name} "
                                f"(${price:.2f} {currency})"
                            )
                            total_items += item.quantity

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"\nOrder: #{saved_order.order_number}"
                            f"\n- Customer: {saved_order.customer.name}"
                            f"\n- Status: {saved_order.state}{status_msg}"
                            f"\n- Order Date: {saved_order.order_date}"
                            f"\n- Items ({total_items}):{''.join(items_summary)}"
                        )
                    )

                    # Add status history display
                    history = saved_order.get_status_history()
                    if history.exists():
                        history_entries = []
                        for entry in history:
                            timestamp = entry.changed_at.strftime('%Y-%m-%d %H:%M:%S')
                            history_entries.append(
                                f"\n  • {timestamp}: {entry.previous_status} → {entry.new_status}" +
                                (f" ({entry.reason})" if entry.reason else "")
                            )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"\n- Status History:{''.join(history_entries)}"
                            )
                        )

                except Exception as e:
                    logger.error(f"Error processing order: {e}")
                    self.stderr.write(
                        self.style.ERROR(f"Failed to process order: {e}")
                    )

            # Handle output options
            if options.get('output') in ['json', 'csv']:
                output_file = options.get('output_file')
                if output_file:
                    self._save_output(orders, options['output'], output_file)
                    self.stdout.write(self.style.SUCCESS(f"Orders saved to {output_file}"))
                    
        except Exception as e:
            logger.error("Error fetching orders: %s", e, exc_info=True)
            raise CommandError(str(e))

    def _build_params(self, options):
        params = {}
        for date_field in ['start_date', 'end_date']:
            if options.get(date_field):
                try:
                    # Validate date format (YYYY-MM-DD)
                    datetime.strptime(options[date_field], '%Y-%m-%d')
                except ValueError:
                    raise CommandError(f"Invalid date format for {date_field}")
                # Map the dates to the parameter names required by the API call
                params_key = 'created_after' if date_field == 'start_date' else 'created_before'
                params[params_key] = options[date_field]
        if options.get("extra_options"):
            try:
                # Parse additional JSON options and merge into params
                extra = json.loads(options["extra_options"])
                params.update(extra)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in extra_options: {e}")
        if options.get('sku'):
            params['sku'] = options['sku']
            
        if options.get('from_ship_date'):
            params['from_expected_ship_date'] = options['from_ship_date']
            
        if options.get('to_ship_date'):
            params['to_expected_ship_date'] = options['to_ship_date']
            
        if options.get('product_info'):
            params['product_info'] = True
            
        return params

    def _save_output(self, orders: list, format_type: str, filename: str):
        """Save orders to file in specified format"""
        if format_type == 'json':
            with open(filename, 'w') as f:
                json.dump(orders, f, indent=2)
        elif format_type == 'csv':
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'order_number', 'customer_name', 'status', 
                    'order_date', 'total_items'
                ])
                writer.writeheader()
                for order in orders:
                    if isinstance(order, dict):
                        writer.writerow({
                            'order_number': order.get('purchaseOrderId'),
                            'customer_name': order.get('shippingInfo', {}).get('postalAddress', {}).get('name'),
                            'status': order.get('status'),
                            'order_date': order.get('orderDate'),
                            'total_items': len(order.get('orderLines', {}).get('orderLine', []))
                        })


# Sample usage:
"""
Order management commands for Walmart CA:

# Basic order operations:
# -----------------------

# Fetch recent orders
python manage.py fetch_orders --platform walmart_ca
python manage.py fetch_orders --platform=walmart_ca --start_date=2025-01-01 --end_date=2025-03-10 

# Fetch orders by date range
python manage.py fetch_orders --platform walmart_ca --from-date 2024-03-01 --to-date 2024-03-09

# Fetch specific order
python manage.py fetch_orders --platform walmart_ca --order-id Y41985711

# Filter orders by status
python manage.py fetch_orders --platform walmart_ca --status Created
python manage.py fetch_orders --platform walmart_ca --status Acknowledged
python manage.py fetch_orders --platform walmart_ca --status Shipped

# Save orders to file
python manage.py fetch_orders --platform walmart_ca --output-file orders.json

# Order processing:
# ---------------

# Perform specific operations on orders
python manage.py manage_order --platform walmart_ca --action status --order-id 123456789
python manage.py manage_order --platform walmart_ca --action acknowledge --order-id 123456789
python manage.py manage_order --platform walmart_ca --action cancel --order-id 123456789 --reason CUSTOMER_CANCELLED

# Ship order with tracking information 
python manage.py manage_order --platform walmart_ca --action ship --order-id 123456789 --carrier UPS --tracking-number 1Z999AA10123456784

# Use data file for shipping (for complex multi-line shipments)
python manage.py manage_order --platform walmart_ca --action ship --order-id 123456789 --data-file shipment.json

# Force processing without validation
python manage.py fetch_orders --platform walmart_ca --force

# Process but don't save to database
python manage.py fetch_orders --platform walmart_ca --dry-run
"""