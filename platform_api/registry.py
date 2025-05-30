from typing import Dict, Type, List
from .base import BasePlatform
from .platforms.walmart_ca.orders import WalmartCAOrders  # Use this for orders

class PlatformRegistry:
    """Registry for marketplace platforms."""
    _platforms: Dict[str, Type[BasePlatform]] = {
        "walmart_ca": WalmartCAOrders,  # Changed to WalmartCAOrders
    }

    @classmethod
    def get_platform(cls, platform_name: str) -> BasePlatform:
        """Get platform API instance"""
        if platform_name == 'walmart_ca':
            # Use the new folder-based structure
            from .platforms.walmart_ca import WalmartCA
            return WalmartCA()
            
        # Try the registry for other platforms
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