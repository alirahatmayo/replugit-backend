"""
Utility functions for the quality control app.
Contains test schemas and shared functionality.
"""

def get_visual_testing_schema():
    """Return the standard schema for visual testing"""
    return {
        "approved": False,
        "exterior_condition": {
            "scratches": "none",  # none, minor, major
            "dents": "none",  # none, minor, major
            "color_consistency": "good",  # poor, fair, good, excellent
            "finish_quality": "good",  # poor, fair, good, excellent
        },
        "display_condition": {
            "dead_pixels": 0,
            "scratches": "none",  # none, minor, major
            "brightness_uniformity": "good",  # poor, fair, good, excellent
            "color_accuracy": "good",  # poor, fair, good, excellent
        },
        "ports_condition": {
            "usb_ports": "functional",  # damaged, loose, functional
            "power_port": "functional",  # damaged, loose, functional
            "hdmi_port": "functional",  # damaged, loose, functional
            "audio_jack": "functional",  # damaged, loose, functional
        },
        "additional_notes": "",
    }

def get_functional_testing_schema():
    """Return the standard schema for functional testing"""
    return {
        "approved": False,
        "power_test": {
            "powers_on": True,
            "boot_time_seconds": 0,
            "stable_operation": True,
        },
        "input_devices": {
            "keyboard_functional": True,
            "touchpad_functional": True,
            "special_keys_functional": True,
        },
        "audio_test": {
            "speakers_functional": True,
            "microphone_functional": True,
            "volume_control_functional": True,
            "audio_quality": "good",  # poor, fair, good, excellent
        },
        "connectivity_test": {
            "wifi_functional": True,
            "bluetooth_functional": True,
            "ethernet_functional": True,
        },
        "software_test": {
            "os_version": "",
            "drivers_installed": True,
            "bios_version": "",
            "firmware_updated": True,
        },
        "additional_notes": "",
    }

def get_electrical_testing_schema():
    """Return the standard schema for electrical testing"""
    return {
        "approved": False,
        "power_supply": {
            "input_voltage_v": 0,
            "output_voltage_v": 0,
            "ripple_mv": 0,
            "functional": True,
        },
        "power_consumption": {
            "idle_watts": 0,
            "load_watts": 0,
            "peak_watts": 0,
            "within_spec": True,
        },
        "temperature": {
            "idle_celsius": 0,
            "load_celsius": 0,
            "thermal_throttling": False,
            "within_spec": True,
        },
        "battery_test": {
            "capacity_mah": 0,
            "cycles": 0,
            "health_percentage": 100,
            "runtime_minutes": 0,
            "charging_functional": True,
        },
        "additional_notes": "",
    }

def get_packaging_testing_schema():
    """Return the standard schema for packaging testing"""
    return {
        "approved": False,
        "box_condition": {
            "integrity": "good",  # damaged, fair, good, excellent
            "appearance": "good",  # poor, fair, good, excellent
            "labeling_correct": True,
        },
        "contents_complete": {
            "main_unit_present": True,
            "power_adapter_present": True,
            "cables_present": True,
            "manuals_present": True,
            "warranty_card_present": True,
        },
        "packaging_materials": {
            "sufficient_protection": True,
            "environmentally_friendly": True,
            "recyclable": True,
        },
        "additional_notes": "",
    }

def get_measurements_schema():
    """Return the standard schema for measurements"""
    return {
        "dimensions": {
            "length_mm": 0,
            "width_mm": 0,
            "height_mm": 0,
        },
        "weight_g": 0,
        "power_consumption_w": {
            "idle": 0,
            "average": 0,
            "peak": 0,
        },
        "performance_metrics": {
            "benchmark_score": 0,
            "boot_time_s": 0,
            "transfer_rate_mbps": 0,
        },
    }

def get_specs_schema():
    """Return the standard schema for device specifications"""
    return {
        "processor": {
            "model": "",
            "speed_ghz": 0,
            "cores": 0,
            "threads": 0,
        },
        "memory": {
            "size_gb": 0,
            "type": "",
            "speed_mhz": 0,
        },
        "storage": {
            "type": "",  # SSD, HDD, eMMC, etc.
            "capacity_gb": 0,
            "interface": "",  # SATA, NVMe, etc.
        },
        "display": {
            "size_inch": 0,
            "resolution": "",
            "panel_type": "",  # IPS, TN, OLED, etc.
            "refresh_rate_hz": 0,
        },
        "graphics": {
            "model": "",
            "memory_gb": 0,
            "type": "",  # Integrated, Dedicated
        },
        "connectivity": {
            "wifi": "",  # Wi-Fi 5, Wi-Fi 6, etc.
            "bluetooth": "",  # 4.0, 5.0, etc.
            "ports": [],  # List of available ports
        },
        "os": {
            "name": "",
            "version": "",
            "build": "",
        },
    }

def initialize_test_schemas(qc_record):
    """Initialize all test fields with default schema values"""
    if not qc_record.visual_testing:
        qc_record.visual_testing = get_visual_testing_schema()
        
    if not qc_record.functional_testing:
        qc_record.functional_testing = get_functional_testing_schema()
        
    if not qc_record.electrical_testing:
        qc_record.electrical_testing = get_electrical_testing_schema()
        
    if not qc_record.packaging_testing:
        qc_record.packaging_testing = get_packaging_testing_schema()
        
    if not qc_record.measurements:
        qc_record.measurements = get_measurements_schema()
        
    if not qc_record.specs:
        qc_record.specs = get_specs_schema()

def initialize_template_schemas(template):
    """Initialize template schemas with default values if not set"""
    if not template.visual_testing_template:
        template.visual_testing_template = get_visual_testing_schema()
    
    if not template.functional_testing_template:
        template.functional_testing_template = get_functional_testing_schema()
        
    if not template.electrical_testing_template:
        template.electrical_testing_template = get_electrical_testing_schema()
        
    if not template.packaging_testing_template:
        template.packaging_testing_template = get_packaging_testing_schema()
        
    if not template.measurements_template:
        template.measurements_template = get_measurements_schema()
        
    if not template.specs_template:
        template.specs_template = get_specs_schema()

def initialize_qc_with_template(qc_record):
    """Initialize QC fields from product-specific template if available"""
    if not qc_record.unit or not hasattr(qc_record.unit, 'product'):
        initialize_test_schemas(qc_record)
        return
    
    # Try to get template for this product
    from .models import ProductQCTemplate
    template = ProductQCTemplate.get_template_for_product(qc_record.unit.product)
    
    if not template:
        # Fall back to default schemas
        initialize_test_schemas(qc_record)
        return
        
    # Apply template schemas
    if not qc_record.visual_testing and template.visual_testing_required:
        qc_record.visual_testing = template.visual_testing_template
        
    if not qc_record.functional_testing and template.functional_testing_required:
        qc_record.functional_testing = template.functional_testing_template
        
    if not qc_record.electrical_testing and template.electrical_testing_required:
        qc_record.electrical_testing = template.electrical_testing_template
        
    if not qc_record.packaging_testing and template.packaging_testing_required:
        qc_record.packaging_testing = template.packaging_testing_template
        
    if not qc_record.measurements:
        qc_record.measurements = template.measurements_template
        
    if not qc_record.specs:
        qc_record.specs = template.specs_template

def merge_testing_data(base, updates):
    """
    Recursively merge two dictionaries, preserving nested structure
    while allowing updates to overwrite base values
    """
    if not isinstance(base, dict) or not isinstance(updates, dict):
        return updates
        
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # If both values are dicts, merge them
            result[key] = merge_testing_data(result[key], value)
        else:
            # Otherwise, update with new value
            result[key] = value
    
    return result

def initialize_with_default_schemas(qc_record):
    """Initialize a ProductUnitQC instance with default schemas"""
    if not qc_record.visual_testing:
        qc_record.visual_testing = get_visual_testing_schema()
        
    if not qc_record.functional_testing:
        qc_record.functional_testing = get_functional_testing_schema()
        
    if not qc_record.electrical_testing:
        qc_record.electrical_testing = get_electrical_testing_schema()
        
    if not qc_record.packaging_testing:
        qc_record.packaging_testing = get_packaging_testing_schema()
        
    if not qc_record.measurements:
        qc_record.measurements = get_measurements_schema()
        
    if not qc_record.specs:
        qc_record.specs = get_specs_schema()