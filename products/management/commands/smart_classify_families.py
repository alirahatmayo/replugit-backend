from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Product, ProductFamily
from products.services.smart_family_classifier import SmartProductFamilyClassifier, apply_smart_family_classification
import csv
import sys
import json


class Command(BaseCommand):
    help = 'Intelligently classify products into product families without needing predefined patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run classification without saving changes',
        )
        parser.add_argument(
            '--confidence',
            type=float,
            default=0.7,
            help='Minimum confidence score (0.0-1.0) to auto-assign products to families',
        )
        parser.add_argument(
            '--similarity',
            type=float,
            default=0.8,
            help='Threshold for considering families similar (0.0-1.0)',
        )
        parser.add_argument(
            '--export-review',
            type=str,
            help='Export products needing review to CSV file',
        )
        parser.add_argument(
            '--export-components',
            type=str,
            help='Export all extracted components to JSON file for analysis',
        )
        parser.add_argument(
            '--create-families',
            action='store_true',
            default=True,
            help='Automatically create product families',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all products, not just those without families',
        )
        parser.add_argument(
            '--test',
            type=str,
            help='Test a single product name for classification without saving',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confidence_threshold = options['confidence']
        similarity_threshold = options['similarity']
        export_file = options.get('export_review')
        export_components = options.get('export_components')
        auto_create = options['create_families']
        process_all = options['all']
        test_product = options.get('test')
        
        # Create classifier
        classifier = SmartProductFamilyClassifier()
        
        # If test mode, just test the single product and exit
        if test_product:
            self.test_classification(classifier, test_product)
            return
            
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in dry-run mode - no changes will be saved"))
        
        # Get the products to process
        if process_all:
            products = Product.objects.all()
            self.stdout.write(f"Processing all {products.count()} products")
        else:
            products = Product.objects.filter(family__isnull=True)
            self.stdout.write(f"Processing {products.count()} products without assigned families")
            
        if products.count() == 0:
            self.stdout.write(self.style.SUCCESS("No products to process"))
            return
            
        # Save component analysis if requested
        component_analysis = []
            
        # Dictionary to collect products by family
        family_products = {}
        needs_review = []
        
        # Statistics
        stats = {
            'processed': products.count(),
            'assigned': 0,
            'skipped': 0,
            'new_families': 0,
            'needs_review': 0,
            'similar_families': 0
        }
        
        # Get existing families for lookup
        existing_families = {f.name.lower(): f for f in ProductFamily.objects.all()}
        created_families = {}
        
        # Create a savepoint for dry-run
        if dry_run:
            sid = transaction.savepoint()
            
        # Classify each product
        for product in products:
            result = classifier.classify_product(product.name)
            
            if not result:
                self.stdout.write(f"  - Could not classify: {product.name}")
                stats['skipped'] += 1
                continue
                
            family_name, confidence, components = result
            family_key = family_name.lower()
            
            # Add to component analysis if requested
            if export_components:
                component_analysis.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'family_name': family_name,
                    'confidence': confidence,
                    'components': components
                })
            
            self.stdout.write(f"  - {product.name} -> {family_name} (confidence: {confidence:.2f})")
            
            if confidence < confidence_threshold:
                needs_review.append((product, family_name, confidence, components))
                stats['needs_review'] += 1
                self.stdout.write(self.style.WARNING(f"    - Below threshold, needs review"))
                continue
                
            # Try to find the family by exact match
            if family_key in existing_families:
                family = existing_families[family_key]
                self.stdout.write(f"    - Using existing family: {family.name}")
            elif family_key in created_families:
                family = created_families[family_key]
                self.stdout.write(f"    - Using newly created family: {family.name}")
            else:
                # Try to find a similar family
                similar_family = classifier.find_similar_family(family_name, existing_families, similarity_threshold)
                
                if similar_family:
                    family = similar_family
                    self.stdout.write(self.style.WARNING(
                        f"    - Using similar family: {family.name} (similarity: {difflib.SequenceMatcher(None, family_name.lower(), family.name.lower()).ratio():.2f})"
                    ))
                    stats['similar_families'] += 1
                elif auto_create:
                    # Create a new family
                    family = ProductFamily.objects.create(
                        name=family_name,
                        description=f"Auto-created family for {family_name} products"
                    )
                    created_families[family_key] = family
                    stats['new_families'] += 1
                    self.stdout.write(self.style.SUCCESS(f"    - Created new family: {family.name}"))
                else:
                    needs_review.append((product, family_name, confidence, components))
                    stats['needs_review'] += 1
                    self.stdout.write(self.style.WARNING(f"    - Not creating families, needs review"))
                    continue
            
            # Assign product to family
            if not dry_run or True:  # Always assign in memory, even in dry run
                product.family = family
                if not dry_run:
                    product.save(update_fields=['family'])
                stats['assigned'] += 1
                
        # If dry run, roll back all changes
        if dry_run:
            transaction.savepoint_rollback(sid)
            self.stdout.write(self.style.WARNING("Dry run complete, all changes have been rolled back"))
        
        # Print statistics
        self.stdout.write("\nClassification results:")
        self.stdout.write(f"  Processed: {stats['processed']}")
        self.stdout.write(f"  Assigned: {stats['assigned']}")
        self.stdout.write(f"  New families created: {stats['new_families']}")
        self.stdout.write(f"  Similar families found: {stats['similar_families']}")
        self.stdout.write(f"  Need review: {stats['needs_review']}")
        self.stdout.write(f"  Skipped (no match): {stats['skipped']}")
        
        # Export needs review list if requested
        if export_file and needs_review:
            with open(export_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Product ID', 'Product Name', 'Suggested Family', 'Confidence', 'Brand', 'Product Line', 'Model Number'])
                
                for product, family, confidence, components in needs_review:
                    writer.writerow([
                        product.id, 
                        product.name, 
                        family, 
                        confidence,
                        components.get('brand', ''),
                        components.get('product_line', ''),
                        components.get('model_number', '')
                    ])
                    
            self.stdout.write(self.style.SUCCESS(f"Exported {len(needs_review)} products needing review to {export_file}"))
            
        # Export component analysis if requested
        if export_components and component_analysis:
            with open(export_components, 'w') as jsonfile:
                json.dump(component_analysis, jsonfile, indent=2)
                
            self.stdout.write(self.style.SUCCESS(f"Exported component analysis for {len(component_analysis)} products to {export_components}"))
            
        if not dry_run:
            self.stdout.write(self.style.SUCCESS("Classification complete!"))
            
    def test_classification(self, classifier, product_name):
        """Test the classification of a single product name."""
        self.stdout.write(self.style.NOTICE(f"Testing classification for: {product_name}"))
        
        result = classifier.classify_product(product_name)
        
        if not result:
            self.stdout.write(self.style.ERROR("Could not classify this product"))
            return
            
        family_name, confidence, components = result
        
        self.stdout.write(self.style.SUCCESS(f"Classification result: {family_name}"))
        self.stdout.write(f"Confidence: {confidence:.2f}")
        self.stdout.write("\nExtracted components:")
        
        for key, value in components.items():
            if key != 'family_key_parts' and value is not None:
                self.stdout.write(f"  {key}: {value}")
                
        self.stdout.write("\nFamily key parts:")
        for part in components.get('family_key_parts', []):
            self.stdout.write(f"  - {part}")
            
        # See if a similar family exists
        existing_families = {f.name.lower(): f for f in ProductFamily.objects.all()}
        similar_family = classifier.find_similar_family(family_name, existing_families)
        
        if similar_family:
            similarity = difflib.SequenceMatcher(None, family_name.lower(), similar_family.name.lower()).ratio()
            self.stdout.write(self.style.WARNING(f"\nSimilar existing family found: {similar_family.name} (similarity: {similarity:.2f})"))
        else:
            self.stdout.write("\nNo similar existing family found")