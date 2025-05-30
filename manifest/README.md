# Manifest Backend Module

This directory contains the backend implementation of the manifest management system for the replugit platform.

## Module Overview

The manifest module handles the processing, validation, and management of supplier manifests, which are detailed documents containing information about products being received into inventory.

## Directory Structure

- **models.py**: Database models for manifests and related entities
- **serializers.py**: Django REST Framework serializers for API responses
- **views.py**: API endpoint implementations
- **urls.py**: URL routing for manifest endpoints
- **services.py**: Business logic for manifest operations
- **services/**: Directory containing specialized service modules
- **batch_service.py**: Service for batch processing of manifests
- **constants.py**: Constants and enumerations used in manifest processing
- **interfaces.py**: Interface definitions for manifest processing
- **templates/**: Template files for manifest-related views
- **admin.py**: Django admin interface configuration
- **migrations/**: Database migrations for manifest models
- **tests.py**: Unit and integration tests

## Key Models

1. **Manifest**: Core model representing an uploaded manifest file
2. **ManifestItem**: Individual items within a manifest
3. **ManifestGroup**: Grouping of similar manifest items with metadata and product family mapping
4. **ManifestTemplate**: Templates defining expected manifest formats
5. **ManifestProcessingJob**: Background jobs for manifest processing

## Manifest Processing Flow

1. Manifest file is uploaded through the API
2. File is validated against templates (if provided)
3. Data is extracted and parsed from the file
4. Manifest items are created from the parsed data
5. Similar items are grouped based on configurable criteria (manufacturer, model, processor, etc.)
6. Group statistics are generated to provide insights into variations within each group
7. Product families are identified and mapped to manifest groups
8. Manifest becomes available for receipt creation

## API Endpoints

- `GET /api/manifests/`: List all manifests
- `POST /api/manifests/`: Upload a new manifest
- `GET /api/manifests/{id}/`: Retrieve manifest details
- `PUT /api/manifests/{id}/`: Update manifest details
- `POST /api/manifests/{id}/map/`: Map manifest items to product families
- `GET /api/manifest-templates/`: List available templates

## Manifest Grouping System

The manifest module includes a grouping system that clusters similar items for improved organization:

### Grouping Criteria

- **Default Grouping Fields**: Items are grouped by manufacturer, model, and processor by default
- **Custom Grouping**: Additional fields can be specified when needed (memory, storage, condition_grade, etc.)
- **Group Hash**: A deterministic hash is created from the grouping fields to ensure consistency

### Group Metadata

The ManifestGroup model uses a JSON metadata field that stores:

1. **Basic Attributes**: Manufacturer, model, processor, memory, storage, condition grade, etc.
2. **Statistical Data**: Information about variations within the group
   - Row numbers from original manifest
   - Memory variations (counts of different configurations)
   - Storage variations (counts of different sizes/types)
   - Condition grade distribution

### Example Group Statistics

```json
{
  "stats": {
    "row_numbers": [5, 12, 18, 22, 35],
    "memory_variations": {
      "8GB": 3,
      "16GB": 2
    },
    "storage_variations": {
      "256GB SSD": 4,
      "512GB SSD": 1 
    },
    "condition_distribution": {
      "A": 3,
      "B": 2
    }
  }
}
```

### Using the ManifestGroupingService

The `ManifestGroupingService` provides methods for working with manifest groups:

```python
# Group items using default grouping fields (manufacturer, model, processor)
result = ManifestGroupingService.group_items(manifest_id)

# Group items using custom grouping fields
result = ManifestGroupingService.group_items(
    manifest_id, 
    group_fields=["manufacturer", "model", "processor", "memory"]
)

# Get all groups for a manifest
groups = ManifestGroupingService.get_groups(manifest_id)
```

## Technical Details

- Implements file processing for CSV, Excel and other formats
- Provides product family matching algorithms
- Supports background processing of large manifests
- Integrates with product catalog for mapping
- Uses JSON metadata for flexible attribute storage
- Implements statistical analysis for grouped items

## Related Modules

- `receiving/`: Receiving module that uses manifests
- `products/`: Product catalog module for family mapping
- `inventory/`: Inventory module for integration

## Recent Changes (May 2025)

### ManifestGroup Model Simplification

The ManifestGroup model has been simplified to function as a true pivot table:

1. **Single Product Family Relationship**: Replaced dual relationship (primary + additional) with a single relationship
2. **JSON Metadata**: Moved variable attributes (processor, memory, storage, etc.) to metadata field
3. **Statistical Analysis**: Added group statistics for variations in memory, storage, and condition
4. **Default Grouping**: Changed default grouping to use manufacturer, model, and processor only
