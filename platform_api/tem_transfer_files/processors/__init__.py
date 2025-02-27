from platform_api.platforms.walmart_ca import WalmartCAProcessor

PLATFORM_PROCESSORS = {
    'walmart_ca': WalmartCAProcessor,
}

def get_processor(platform: str):
    if platform not in PLATFORM_PROCESSORS:
        raise ValueError(f"Unsupported platform: {platform}")
    return PLATFORM_PROCESSORS[platform]()