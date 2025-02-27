from typing import Dict, Type, List
from .base import BasePlatform
from .walmart_ca.api import WalmartCAPlatform
# from .amazon_us.api import AmazonUSPlatform
# from .shopify.api import ShopifyPlatform

class PlatformRegistry:
    """Registry for marketplace platforms."""
    _platforms: Dict[str, Type[BasePlatform]] = {
        "walmart_ca": WalmartCAPlatform,
        # "amazon_us": AmazonUSPlatform,
        # "shopify": ShopifyPlatform,
    }

    @classmethod
    def get_platform(cls, platform_name: str) -> BasePlatform:
        platform_class = cls._platforms.get(platform_name)
        if not platform_class:
            raise ValueError(f"Unknown platform: {platform_name}")
        return platform_class()

    @classmethod
    def register_platform(cls, name: str, platform_class: Type[BasePlatform]) -> None:
        cls._platforms[name] = platform_class

    @classmethod
    def list_platforms(cls) -> List[str]:
        return list(cls._platforms.keys())