import json
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from platform_api.registry import PlatformRegistry
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Perform operations on orders (acknowledge, ship, cancel)
    """
    help = "Perform operations on marketplace orders"

    def add_arguments(self, parser):
        parser.add_argument('--platform', required=True, help='Platform key (e.g., walmart_ca)')
        parser.add_argument('--operation', required=True, 
                           choices=['acknowledge', 'ship', 'cancel'], 
                           help='Operation to perform')
        parser.add_argument('--order', required=True, help='Order number to operate on')
        parser.add_argument('--lines', help='Line numbers (comma-separated)')
        parser.add_argument('--tracking', help='Tracking number (for shipping)')
        parser.add_argument('--carrier', help='Carrier name (for shipping)')
        parser.add_argument('--reason', help='Reason (for cancellation)')

    def handle(self, *args, **options):
        platform_key = options['platform']
        operation = options['operation']
        order_id = options['order']
        
        try:
            platform_api = PlatformRegistry.get_platform(platform_key)
            
            # Fetch order first
            self.stdout.write(f"Fetching order {order_id} from {platform_key}...")
            order_data = platform_api.get_order(order_id, process=False)
            
            if not order_data:
                self.stderr.write(self.style.ERROR(f"Order {order_id} not found"))
                return
            
            # Pretty print the first few fields of the response for debugging
            self.stdout.write("Order data structure:")
            self.stdout.write(json.dumps({k: v for i, (k, v) in enumerate(order_data.items()) if i < 5}, indent=2))

            # Get line numbers with better error handling
            line_numbers = []
            if options.get('lines'):
                line_numbers = options['lines'].split(',')
            else:
                try:
                    line_numbers = platform_api.get_order_line_numbers(order_data)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error extracting line numbers: {str(e)}"))
                    return
                
            if not line_numbers:
                self.stderr.write(self.style.ERROR(f"No line items found for order {order_id}"))
                self.stderr.write(self.style.WARNING("You can specify line numbers manually with the --lines parameter"))
                return
                
            # Perform operation
            if operation == 'acknowledge':
                self._acknowledge_order(platform_api, order_id)
            elif operation == 'ship':
                self._ship_order(platform_api, order_id, line_numbers, options)
            elif operation == 'cancel':
                self._cancel_order(platform_api, order_id, line_numbers, options)
                
        except Exception as e:
            logger.error("Error performing order operation: %s", e, exc_info=True)
            raise CommandError(str(e))
            
    def _acknowledge_order(self, platform_api, order_id):
        """Acknowledge an order"""
        self.stdout.write(f"Acknowledging order {order_id}...")
        response = platform_api.acknowledge_order(order_id)
        
        self.stdout.write(self.style.SUCCESS(f"Order {order_id} acknowledged successfully"))
        return response
        
    def _ship_order(self, platform_api, order_id, line_numbers, options):
        """Ship an order"""
        if not options.get('tracking'):
            self.stderr.write(self.style.ERROR("--tracking parameter is required for shipping"))
            return
            
        carrier = options.get('carrier', 'OTHER')
        tracking = options['tracking']
        ship_date = datetime.now()
        
        self.stdout.write(
            f"Shipping order {order_id} with carrier {carrier}, "
            f"tracking {tracking}, lines: {', '.join(line_numbers)}"
        )
        
        response = platform_api.ship_order(
            order_id, 
            line_numbers,
            carrier,
            tracking,
            ship_date
        )
        
        self.stdout.write(self.style.SUCCESS(f"Order {order_id} shipped successfully"))
        return response
        
    def _cancel_order(self, platform_api, order_id, line_numbers, options):
        """Cancel an order"""
        # Update the valid reasons list to include CANCEL_BY_SELLER
        valid_reasons = ['CUSTOMER_CANCELLED', 'INVENTORY_CONSTRAINT', 
                         'PRICE_ERROR', 'SHIPPING_CONSTRAINT', 'OTHER',
                         'CANCEL_BY_SELLER']  # Added CANCEL_BY_SELLER
        
        reason = options.get('reason', 'CUSTOMER_CANCELLED').upper()
        
        if reason not in valid_reasons:
            self.stdout.write(self.style.WARNING(
                f"Invalid cancellation reason: {reason}. Using OTHER instead."
            ))
            reason = 'OTHER'
        
        self.stdout.write(
            f"Cancelling order {order_id}, lines: {', '.join(line_numbers)}, "
            f"reason: {reason}"
        )
        
        response = platform_api.cancel_order(
            order_id,
            line_numbers,
            reason
        )
        
        # Improve response handling to debug 520 error
        if response and response.get('orderCancellationResponse'):
            # Check for errors in the response
            if response.get('orderCancellationResponse', {}).get('errors'):
                errors = response['orderCancellationResponse']['errors']
                self.stderr.write(self.style.ERROR(f"Cancellation errors: {errors}"))
                return
            
            self.stdout.write(self.style.SUCCESS(f"Order {order_id} cancelled successfully"))
        else:
            # Print more details about the response for diagnosis
            self.stderr.write(self.style.ERROR(f"Received unexpected response format. Status Code: {response.get('status', 'Unknown')}"))
            self.stderr.write(f"Response content: {json.dumps(response, indent=2)[:1000]}...")
        
        return response
    

    # Add to cancel_order method
    def cancel_order(
        self,
        purchase_order_id: str,
        line_numbers: List[str],
        cancel_reason: str,
        quantities: Dict[str, int] = None  # Optional quantities by line number
    ):
        # ... existing code

        # Use specified quantities or default to full cancellation
        order_lines = []
        for line_num in line_numbers:
            quantity = str(quantities.get(line_num, 1)) if quantities else "1"
            order_lines.append({
                "lineNumber": line_num,
                "orderLineStatuses": {
                    "orderLineStatus": [{
                        "status": "Cancelled",
                        "cancellationReason": cancel_reason,
                        "statusQuantity": {
                            "amount": quantity,  # Use dynamic quantity
                            "unitOfMeasurement": "EACH"
                        }
                    }]
                }
            })


    #------Commands------
    # python manage.py order_operations --platform walmart_ca --operation acknowledge --order 123456
    # python manage.py order_operations --platform walmart_ca --operation ship --order 123456 --lines 1,2 --tracking 123456 --carrier UPS
    # python manage.py order_operations --platform walmart_ca --operation cancel --order 123456 --lines 1,2 --reason CUSTOMER_CANCELLED     
    #