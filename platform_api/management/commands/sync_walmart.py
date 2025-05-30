from django.core.management.base import BaseCommand
import logging
from datetime import datetime, timedelta
import subprocess

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Scheduled sync for Walmart CA products and orders"
    
    def add_arguments(self, parser):
        parser.add_argument("--resource", choices=['orders', 'products', 'all'], 
                           default='all', help="Resource to sync")
        parser.add_argument("--days", type=int, default=3, 
                           help="Number of days to look back for orders")
    
    def handle(self, *args, **options):
        resource = options['resource']
        days = options['days']
        
        self.stdout.write(f"Starting Walmart CA sync at {datetime.now().isoformat()}")
        
        if resource in ['all', 'orders']:
            self._sync_orders(days)
            
        if resource in ['all', 'products']:
            self._sync_products()
            
        self.stdout.write(self.style.SUCCESS(f"Sync completed at {datetime.now().isoformat()}"))
    
    def _sync_orders(self, days):
        """Sync recent orders"""
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        self.stdout.write(f"Syncing orders from {start_date} to {end_date}")
        
        cmd = [
            "python", "manage.py", "fetch_orders",
            "--platform", "walmart_ca",
            "--start_date", start_date,
            "--end_date", end_date,
            "--all-pages"
        ]
        
        subprocess.run(cmd, check=True)
    
    def _sync_products(self):
        """Sync active products"""
        self.stdout.write("Syncing all active products")
        
        cmd = [
            "python", "manage.py", "fetch_products",
            "--platform", "walmart_ca",
            "--operation", "fetch-all",
            "--status", "ACTIVE",
            "--limit", "50"
        ]
        
        subprocess.run(cmd, check=True)