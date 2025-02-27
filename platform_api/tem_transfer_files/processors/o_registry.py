from typing import Type
from .base_product import BaseProductProcessor
from .walmart_ca_product import WalmartCAProductProcessor

class ProductProcessorRegistry:
    """Registry for platform-specific product processors"""
    
    _processors = {
        'walmart_ca': WalmartCAProductProcessor,
    }

    @classmethod
    def get_processor(cls, platform: str) -> BaseProductProcessor:
        """Get product processor for specified platform"""
        processor_class = cls._processors.get(platform)
        if not processor_class:
            raise ValueError(f"No product processor found for platform: {platform}")
        return processor_class()

    @classmethod
    def register_processor(cls, platform: str, processor: Type[BaseProductProcessor]) -> None:
        """Register a new product processor"""
        cls._processors[platform] = processor