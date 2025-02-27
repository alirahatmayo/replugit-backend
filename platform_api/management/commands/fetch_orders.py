from django.core.management.base import BaseCommand, CommandError
import logging
import json
from datetime import datetime
from time import sleep
from decimal import Decimal

# Import our new processor getter and platform registry
from platform_api.platforms.walmart_ca.processor import WalmartCAProcessor
from platform_api.registry import PlatformRegistry

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

    def handle(self, *args, **options):
        """Handle command execution"""
        platform_key = options.get("platform")
        if not platform_key:
            raise CommandError("Platform parameter is required")

        order_id = options.get("order_id")
        # Instantiate the processor based on the platform key
        if platform_key.lower() == "walmart_ca":
            processor = WalmartCAProcessor()
        else:
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
                try:
                    processed_order = processor.process_order(order_data)
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
                            price = Decimal(price_data.get('amount', '0.00'))
                            currency = price_data.get('currency', 'CAD')
                            if price > 0:
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


#----Commands----
# python manage.py fetch_orders --platform=walmart_ca --start_date=2022-01-01 --end_date=2022-01-31 --output=console
# python manage.py fetch_orders --platform=walmart_ca --start_date=2025-01-01 --end_date=2025-02-31 --output=json --output-file=orders.json
# python manage.py fetch_orders --platform=walmart_ca --start_date=2022-01-01 --end_date=2022-01-31 --output=csv --output-file=orders.csv
# python manage.py fetch_orders --platform=walmart_ca --start_date=2022-01-01 --end_date=2022-01-31 --output=console --dry-run
# python manage.py fetch_orders --platform=walmart_ca --start_date=2022-01-01 --end_date=2022-01-31 --output=console --status=pending
# python manage.py fetch_orders --platform=walmart_ca --start_date=2022-01-01 --end_date=2022-01-31 --output=console --status=shipped
# python manage.py fetch_order_By_id