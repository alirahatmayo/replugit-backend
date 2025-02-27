# processors/registry/product.py
from typing import Dict, Type, List
# from platform_api.processors.base.product import BaseProductProcessor
from ..base.product import BaseProductProcessor


class ProductProcessorRegistry:
    _processors: Dict[str, Type[BaseProductProcessor]] = {}

    @classmethod
    def register_processor(cls, platform: str, processor: Type[BaseProductProcessor]) -> None:
        cls._processors[platform] = processor

    @classmethod
    def get_processor(cls, platform: str) -> BaseProductProcessor:
        processor_class = cls._processors.get(platform)
        if not processor_class:
            raise ValueError(f"No product processor registered for platform {platform}")
        return processor_class()

    @classmethod
    def list_processors(cls) -> List[str]:
        return list(cls._processors.keys())
