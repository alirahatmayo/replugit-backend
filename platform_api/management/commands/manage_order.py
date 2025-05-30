from django.core.management.base import BaseCommand, CommandError
import json
from datetime import datetime

class Command(BaseCommand):
    help = "Manage Walmart CA orders (acknowledge, ship, cancel)"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, default="walmart_ca", help="Platform identifier")
        parser.add_argument("--action", type=str, required=True, 
                           choices=['acknowledge', 'ship', 'cancel', 'status'],
                           help="Action to perform")
        parser.add_argument("--order-id", type=str, required=True, help="Order ID to act upon")
        parser.add_argument("--line-number", type=str, help="Line number for specific line actions")
        parser.add_argument("--data-file", type=str, help="JSON file with action data")
        
        # Shipping specific
        parser.add_argument("--tracking-number", type=str, help="Tracking number for shipping updates")
        parser.add_argument("--carrier", type=str, help="Carrier name for shipping updates")
        
        # Cancellation specific
        parser.add_argument("--reason", type=str, help="Cancellation reason")
        
    def handle(self, *args, **options):
        platform_key = options.get("platform")
        action = options.get("action")
        order_id = options.get("order_id")
        
        # Get platform API
        from platform_api.platforms.walmart_ca import WalmartCA
        platform = WalmartCA()
        
        if action == 'acknowledge':
            self.acknowledge_order(platform, order_id, options)
        elif action == 'ship':
            self.ship_order(platform, order_id, options)
        elif action == 'cancel':
            self.cancel_order(platform, order_id, options)
        elif action == 'status':
            self.get_order_status(platform, order_id)
            
    def acknowledge_order(self, platform, order_id, options):
        """Acknowledge an order"""
        line_numbers = None
        if options.get('line_number'):
            line_numbers = [options['line_number']]
            
        response = platform.orders.acknowledge_order(order_id, line_numbers)
        self.stdout.write(self.style.SUCCESS(f"Order {order_id} acknowledged successfully"))
        self.stdout.write(json.dumps(response, indent=2))
        
    def ship_order(self, platform, order_id, options):
        """Add shipping information to an order"""
        # Get shipping info from arguments or file
        shipping_info = []
        
        if options.get('data_file'):
            with open(options['data_file'], 'r') as f:
                shipping_info = json.load(f)
        else:
            # Create from command line args
            line_info = {
                'line_number': options.get('line_number', '1'),
                'tracking_number': options.get('tracking_number'),
                'carrier_name': options.get('carrier', 'OTHER'),
                'ship_date_time': datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
            
            # Validate required fields
            if not line_info['tracking_number']:
                raise CommandError("--tracking-number is required for shipping updates")
                
            shipping_info.append(line_info)
            
        response = platform.orders.ship_order(order_id, shipping_info)
        self.stdout.write(self.style.SUCCESS(f"Shipping information added to order {order_id}"))
        self.stdout.write(json.dumps(response, indent=2))
        
    def cancel_order(self, platform, order_id, options):
        """Cancel order lines"""
        cancellations = []
        
        if options.get('data_file'):
            with open(options['data_file'], 'r') as f:
                cancellations = json.load(f)
        else:
            # Get the reason - enforce valid values
            reason = options.get('reason', 'CANCEL_BY_SELLER')
            if reason not in ["CANCEL_BY_SELLER", "CUSTOMER_REQUESTED_SELLER_TO_CANCEL"]:
                self.stderr.write(self.style.WARNING(f"Invalid reason '{reason}'. Using CANCEL_BY_SELLER."))
                reason = "CANCEL_BY_SELLER"
                
            # Create from command line args
            cancel_info = {
                'line_number': options.get('line_number', '1'),
                'reason': reason
            }
            cancellations.append(cancel_info)
            
        response = platform.orders.cancel_order(order_id, cancellations)
        self.stdout.write(self.style.SUCCESS(f"Order {order_id} cancelled successfully"))
        self.stdout.write(json.dumps(response, indent=2))
        
    def get_order_status(self, platform, order_id):
        """Get current order status"""
        order = platform.api.get_order(order_id)
        self.stdout.write(json.dumps(order, indent=2))