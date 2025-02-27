from django.core.management.base import BaseCommand
from platform_api.registry import PlatformRegistry
import logging
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    console.log("Fetch products from a specified platform")
    help = "Fetch orders from a specified platform"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, required=True, help="Platform identifier (e.g., walmart_ca, amazon_us, shopify)")
        parser.add_argument("--start_date", type=str, help="Start date in ISO format (YYYY-MM-DD)")
        parser.add_argument("--end_date", type=str, help="End date in ISO format (YYYY-MM-DD)")
        parser.add_argument("--extra_options", type=str, help="Extra JSON parameters for platform-specific options")

    def handle(self, *args, **options):
        platform_key = options.get("platform")
        try:
            platform = PlatformRegistry.get_platform(platform_key)
            params = {}
            if options.get("start_date"):
                params["created_after"] = options["start_date"]
            if options.get("end_date"):
                params["created_before"] = options["end_date"]
            if options.get("extra_options"):
                extra = json.loads(options["extra_options"])
                params.update(extra)
            orders = platform.fetch_orders(**params)
            self.stdout.write(self.style.SUCCESS(f"Successfully fetched {len(orders)} orders from {platform_key}"))
        except Exception as e:
            logger.error("Error fetching orders: %s", e)
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
