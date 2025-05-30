"""
Constants and configuration for the manifest module
"""

# System fields available for column mapping
SYSTEM_FIELDS = [
    {
        "value": "not_mapped",
        "label": "Not Mapped",
        "group": "general",
        "data_type": "any",
        "description": "Field will not be mapped to any system attribute",
        "is_required": False,
        "patterns": ["ignore", "skip", "none", "notmapped", "not_mapped"]
    },
    {
        "value": "barcode",
        "label": "Barcode / Asset ID",
        "group": "identification",
        "data_type": "string",
        "description": "Unique identifier or barcode for the asset",
        "is_required": False,
        "patterns": ["barcode", "barcodeid", "barcode_id", "bcode", "upc", "sku", "scan", "product id", "productid", "asset_id", "assetid", "asset number", "assetnumber"]
    },
    {
        "value": "serial",
        "label": "Serial Number",
        "group": "identification",
        "data_type": "string",
        "description": "Serial number of the device",
        "is_required": True,
        "patterns": ["serial", "serialnumber", "serial_number", "serialnum", "sn", "serial number", "serialno", "serial no", "service tag", "servicetag"]
    },
    {
        "value": "manufacturer",
        "label": "Manufacturer",
        "group": "basic_info",
        "data_type": "string",
        "description": "Manufacturer or brand of the device",
        "is_required": True,
        "patterns": ["manufacturer", "brand", "make", "oem", "vendor", "mfg", "mfr", "company"]
    },
    {
        "value": "model",
        "label": "Model",
        "group": "basic_info",
        "data_type": "string",
        "description": "Model name/number of the device",
        "is_required": True,
        "patterns": ["model", "modelname", "model_name", "model_number", "modelnumber", "model number", "modelno", "model no", "product model"]
    },
    {
        "value": "processor",
        "label": "Processor Type",
        "group": "specifications",
        "data_type": "string",
        "description": "CPU/Processor model of the device",
        "is_required": False,
        "patterns": ["processor", "cpu", "proc", "chipset", "chip", "processeur", "central processing unit", "processor type", "processor model"]
    },
    {
        "value": "cpu",
        "label": "CPU Speed",
        "group": "specifications",
        "data_type": "string",
        "description": "CPU speed in GHz",
        "is_required": False,
        "patterns": ["cpu speed", "cpu frequency", "ghz", "processor speed", "clock speed", "cpu_speed", "cpuspeed", "freq"]
    },
    {
        "value": "memory",
        "label": "Memory (RAM)",
        "group": "specifications",
        "data_type": "string",
        "description": "RAM size (e.g., 8GB)",
        "is_required": False,
        "patterns": ["memory", "ram", "mem", "memory_size", "memorysize", "memory size", "memory_capacity", "ram size", "ramsize", "ram capacity", "memory amount"]
    },
    {
        "value": "storage",
        "label": "Storage (HDD/SSD)",
        "group": "specifications",
        "data_type": "string",
        "description": "Storage capacity and type",
        "is_required": False,
        "patterns": ["storage", "hdd", "ssd", "disk", "drive", "harddrive", "storagecapacity", "storage capacity", "storage_capacity", "disk size", "disksize", "ssd capacity", "hdd capacity"]
    },
    {
        "value": "battery",
        "label": "Battery Status",
        "group": "condition",
        "data_type": "string",
        "description": "Battery health condition",
        "is_required": False,
        "patterns": ["battery", "battery health", "battery status", "bat", "battery condition", "battery_status", "bat health"]
    },
    {
        "value": "condition_grade",
        "label": "Condition Grade",
        "group": "condition",
        "data_type": "string",
        "description": "Overall condition grade (e.g., A, B, C)",
        "is_required": False,
        "patterns": ["condition", "grade", "quality", "conditiongrade", "condition_grade", "cond", "rating", "state", "condition rating"]
    },
    {
        "value": "condition_notes",
        "label": "Condition Notes",
        "group": "condition",
        "data_type": "string",
        "description": "Detailed notes about device condition",
        "is_required": False,
        "patterns": ["notes", "description", "comment", "comments", "memo", "details", "remark", "remarks", "desc", "condition notes", "conditionnotes", "condition_notes", "condition description"]
    },
    {
        "value": "unit_price",
        "label": "Price",
        "group": "pricing",
        "data_type": "decimal",
        "description": "Unit price of the item",
        "is_required": False,
        "patterns": ["price", "cost", "value", "unitprice", "unit_price", "msrp", "retail", "retail_price", "selling price", "sellingprice", "sale price", "saleprice", "unit cost"]
    }
]

# Field groups for organizing system fields
FIELD_GROUPS = {
    "identification": {
        "label": "Identification",
        "description": "Fields used to uniquely identify assets",
        "order": 1
    },
    "basic_info": {
        "label": "Basic Information",
        "description": "Core details about the device",
        "order": 2
    },
    "specifications": {
        "label": "Specifications",
        "description": "Technical specifications of the device",
        "order": 3
    },
    "condition": {
        "label": "Condition",
        "description": "Information about the physical condition",
        "order": 4
    },
    "pricing": {
        "label": "Pricing",
        "description": "Price and value related information",
        "order": 5
    },
    "general": {
        "label": "General",
        "description": "General purpose fields",
        "order": 6
    }
}