# processor/registry/order.py
from typing import Dict, Type
from ..base.order import BaseOrderProcessor

class OrderProcessorRegistry:
    """Registry for order processors."""
    _processors = {}  # Simplified storage

    @classmethod
    def register(cls, platform: str, processor: Type[BaseOrderProcessor]) -> None:
        """Register a processor for a platform"""
        cls._processors[platform] = processor

    @classmethod
    def get_processor(cls, platform: str) -> BaseOrderProcessor:
        """Get a processor instance for a platform"""
        if platform not in cls._processors:
            raise ValueError(f"No processor for platform: {platform}")
        return cls._processors[platform]()

    @classmethod
    def list_processors(cls) -> list[str]:
        """List all registered processors"""
        return list(cls._processors.keys())