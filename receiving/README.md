# Receiving Backend Module

This directory contains the backend implementation of the inventory receiving system for the replugit platform.

## Module Overview

The receiving module handles all server-side processing related to inventory intake, including:

- Manifest processing and validation
- Receipt creation and management
- Integration with inventory and product systems
- Data validation and transformation

## Directory Structure

- **models.py**: Database models for receipts, manifests, and related entities
- **serializers.py**: Django REST Framework serializers for API responses
- **views.py**: API endpoint implementations
- **urls.py**: URL routing for receiving endpoints
- **services.py**: Business logic for receiving operations
- **admin.py**: Django admin interface configuration
- **migrations/**: Database migrations for receiving models
- **tests.py**: Unit and integration tests

## Key Models

1. **Receipt**: Records of physical inventory receipt
2. **Manifest**: Detailed records of expected items from suppliers
3. **ManifestTemplate**: Template definitions for standardizing manifest formats
4. **ReceiptItem**: Individual items within a receipt

## Batch Receipt Destination Workflow

The system now supports a flexible routing workflow for received items, allowing them to be sent to different destinations:

### Destination Options

- **Inventory**: Items are sent directly to inventory without QC inspection
- **Quality Control**: Items are routed to QC for inspection before entering inventory
- **Pending**: Decision on destination is pending (default state)

### Model Implementation

The `BatchItem` model includes:
- `destination` field with choices: 'inventory', 'qc', 'pending'
- Integration with the existing `requires_unit_qc` field for backward compatibility

### Workflow Process

1. When a batch is received, items default to 'pending' destination
2. Users can update destination for:
   - Individual items using `BatchItemViewSet.update_destination`
   - Multiple items at once using `BatchItemViewSet.bulk_update_destination`
   - All items in a batch using `ReceiptBatchViewSet.update_batch_destinations`
3. During batch processing:
   - Items marked for 'inventory' are created directly in inventory
   - Items marked for 'qc' are routed to Quality Control system
   - Items still 'pending' are skipped until a destination is assigned

### API Endpoints

- `POST /api/batch-items/{id}/update_destination/`: Update destination for a single item
- `POST /api/batch-items/bulk_update_destination/`: Bulk update destinations for multiple items
- `POST /api/receipt-batches/{id}/update_batch_destinations/`: Update destination for all items in a batch

## API Endpoints

- `GET /api/receipts/`: List all receipts
- `POST /api/receipts/`: Create a new receipt
- `GET /api/receipts/{id}/`: Retrieve receipt details
- `PUT /api/receipts/{id}/`: Update receipt details
- `GET /api/manifests/`: List all manifests
- `POST /api/manifests/`: Create/upload a new manifest
- `GET /api/manifests/{id}/`: Retrieve manifest details

## Workflow Integration

The receiving module integrates with:
- Products module for product data
- Inventory module for inventory updates
- Quality Control module for QC processes

## Technical Details

- Built on Django and Django REST Framework
- Follows service-oriented architecture patterns
- Implements comprehensive data validation
- Integrates with file processing for manifest uploads

## Related Modules

- `inventory/`: Inventory management module
- `products/`: Product catalog module
- `quality_control/`: Quality control processes
