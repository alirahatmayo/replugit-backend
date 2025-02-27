from .order import OrderProcessorRegistry
from .product import ProductProcessorRegistry
from ..platforms.walmart_ca.order import WalmartCAOrderProcessor
from ..platforms.walmart_ca.product import WalmartCAProductProcessor

# Register the Walmart Canada processor
OrderProcessorRegistry.register_processor("walmart_ca", WalmartCAOrderProcessor)

ProductProcessorRegistry.register_processor("walmart_ca", WalmartCAProductProcessor)