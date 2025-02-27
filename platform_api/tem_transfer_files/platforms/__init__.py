# from .walmart_us.processor import WalmartUSProcessor
# from .walmart_ca.processor import WalmartCAProcessor
# from platform_api.services import OrderService

# PLATFORM_PROCESSORS = {
#     'walmart_us': WalmartUSProcessor,
#     'walmart_ca': WalmartCAProcessor,
# }

# def get_processor(platform: str):
#     """Get appropriate processor for platform"""
#     if platform not in PLATFORM_PROCESSORS:
#         raise ValueError(f"Unsupported platform: {platform}")
#     return PLATFORM_PROCESSORS[platform]()

# # Process orders
# us_order = OrderService.process_order('walmart_us', order_data)
# ca_order = OrderService.process_order('walmart_ca', order_data)
