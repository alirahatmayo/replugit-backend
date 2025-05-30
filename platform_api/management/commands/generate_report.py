from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from orders.models import Order
from products.models import Product
import csv
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = "Generate reports on products and orders"
    
    def add_arguments(self, parser):
        parser.add_argument("--report-type", choices=['sales', 'inventory', 'performance'], 
                          required=True, help="Type of report to generate")
        parser.add_argument("--days", type=int, default=30, help="Days to include in report")
        parser.add_argument("--output", type=str, required=True, help="Output file path")
    
    def handle(self, *args, **options):
        report_type = options['report_type']
        days = options['days']
        output = options['output']
        
        if report_type == 'sales':
            self._generate_sales_report(days, output)
        elif report_type == 'inventory':
            self._generate_inventory_report(output)
        elif report_type == 'performance':
            self._generate_performance_report(days, output)
    
    def _generate_sales_report(self, days, output):
        """Generate sales report by product"""
        start_date = datetime.now() - timedelta(days=days)
        
        # Get all orders from specified period
        orders = Order.objects.filter(
            order_date__gte=start_date,
            platform='walmart_ca'
        )
        
        # Aggregate sales by product
        sales_data = {}
        
        for order in orders:
            for item in order.items.all():
                if item.product_id not in sales_data:
                    sales_data[item.product_id] = {
                        'sku': item.product.sku,
                        'name': item.product.name,
                        'quantity': 0,
                        'revenue': 0,
                    }
                
                sales_data[item.product_id]['quantity'] += item.quantity
                
                # Extract revenue from price_data
                if item.price_data and 'totals' in item.price_data:
                    revenue = float(item.price_data['totals'].get('grand_total', 0))
                    sales_data[item.product_id]['revenue'] += revenue
        
        # Write to CSV
        with open(output, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['SKU', 'Product Name', 'Units Sold', 'Revenue'])
            
            for product_id, data in sales_data.items():
                writer.writerow([
                    data['sku'],
                    data['name'],
                    data['quantity'],
                    f"${data['revenue']:.2f}"
                ])
        
        self.stdout.write(self.style.SUCCESS(f"Sales report generated at {output}"))