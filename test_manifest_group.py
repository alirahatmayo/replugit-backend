"""
Quick test script to verify that our ManifestGroup model works correctly
with the metadata JSON field.
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'replugit.settings')
django.setup()

from manifest.models import ManifestGroup, Manifest

def test_manifest_group():
    """Test the ManifestGroup model functionality"""
    print("Testing ManifestGroup model with metadata field...")
    
    # Get or create a test manifest
    test_manifest, created = Manifest.objects.get_or_create(
        name="Test Manifest for Group Tests",
        defaults={
            "status": "pending",
            "file_type": "csv",
        }
    )
    print(f"Using {'new' if created else 'existing'} test manifest: {test_manifest.name} (ID: {test_manifest.id})")
    
    # Create a test group with metadata
    test_metadata = {
        "processor": "Intel i7-1165G7",
        "memory": "16GB",
        "storage": "512GB SSD",
        "condition_grade": "A",
        "test_key": "test_value"
    }
    
    test_group = ManifestGroup(
        manifest=test_manifest,
        manufacturer="Dell",
        model="XPS 13",
        quantity=5,
        metadata=test_metadata
    )
    
    # Save and verify it generates a group_key
    test_group.save()
    print(f"Created test group: {test_group}")
    print(f"Generated group_key: {test_group.group_key}")
    
    # Test the metadata helper methods
    print("\nTesting metadata helper methods:")
    print(f"get_metadata('processor'): {test_group.get_metadata('processor')}")
    print(f"get_metadata('memory'): {test_group.get_metadata('memory')}")
    print(f"get_metadata('nonexistent', 'default'): {test_group.get_metadata('nonexistent', 'default')}")
    
    # Test setting metadata
    test_group.set_metadata("new_key", "new_value")
    test_group.save()
    print(f"\nAfter setting 'new_key': {json.dumps(test_group.metadata, indent=2)}")
    
    # Test group key generation with the metadata
    print(f"\nGroup key based on metadata: {test_group.generate_group_key()}")
    
    return test_group

if __name__ == "__main__":
    test_manifest_group = test_manifest_group()
    print("\nTest completed successfully!")
