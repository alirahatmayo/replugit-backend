import re
from collections import defaultdict
import logging
from typing import Dict, List, Optional, Tuple
import string
import difflib

from products.models import Product, ProductFamily

logger = logging.getLogger(__name__)

class SmartProductFamilyClassifier:
    """
    Automatically assigns products to specific product families using a dynamic pattern recognition
    approach that doesn't require predefined patterns for each model.
    
    Key features:
    1. Extract key product identifiers using regex and NLP techniques
    2. Group similar products based on brand, series, and model numbers
    3. Dynamically create families for previously unseen products
    """
    
    # Core brand patterns
    BRANDS = [
        'lenovo', 'dell', 'hp', 'samsung', 'sony', 'google', 'microsoft', 
        'playstation', 'asus', 'oneplus', 'hisense', 'acer', 'alienware'
    ]
    
    # Core product lines
    PRODUCT_LINES = [
        'thinkpad', 'ideapad', 'latitude', 'elitebook', 'probook', 'galaxy', 
        'pixel', 'surface', 'playstation', 'nest', 'chromebook', 'inspiron',
        'optiplex', 'xps'
    ]
    
    # Form factors
    FORM_FACTORS = [
        'laptop', 'notebook', 'desktop', 'ultrabook', 'tablet', 'smartphone',
        'monitor', 'console', '2-in-1', 'convertible', 'all-in-one', 'aio'
    ]
    
    # Series identifiers - common patterns for model series
    SERIES_PATTERNS = {
        # Common laptop series patterns
        'thinkpad_t': r'thinkpad\s+t\d{3}[s]?',
        'thinkpad_x': r'thinkpad\s+x\d{3}[s]?',
        'thinkpad_l': r'thinkpad\s+l\d{3}[s]?',
        'thinkpad_p': r'thinkpad\s+p\d{2,3}[s]?',
        'latitude_series': r'latitude\s+\d{4}',
        'latitude_generation': r'latitude\s+\d{4}',
        'elitebook_series': r'elitebook\s+\d{3}\s+g\d',
        
        # Phone series patterns
        'galaxy_s': r'galaxy\s+s\d{1,2}',
        'galaxy_a': r'galaxy\s+a\d{1,2}',
        'galaxy_z': r'galaxy\s+z',
        'pixel_series': r'pixel\s+\d',
        
        # Other device patterns
        'surface_pro': r'surface\s+pro\s+\d',
        'playstation': r'playstation\s*\d',
    }
    
    def __init__(self):
        # Compile regexes for brands
        self.brand_patterns = {brand: re.compile(rf'\b{re.escape(brand)}\b', re.IGNORECASE) 
                               for brand in self.BRANDS}
        
        # Compile regexes for product lines
        self.product_line_patterns = {line: re.compile(rf'\b{re.escape(line)}\b', re.IGNORECASE) 
                                     for line in self.PRODUCT_LINES}
        
        # Compile regex for form factors
        self.form_factor_patterns = {factor: re.compile(rf'\b{re.escape(factor)}\b', re.IGNORECASE) 
                                    for factor in self.FORM_FACTORS}
        
        # Compile regexes for series patterns
        self.series_patterns = {k: re.compile(v, re.IGNORECASE) 
                                for k, v in self.SERIES_PATTERNS.items()}
        
        # Model number extraction patterns
        self.model_number_patterns = [
            # ThinkPad T490, Latitude 5490, etc.
            re.compile(r'(?P<base>[a-zA-Z]+)\s*(?P<model>[a-zA-Z]?\d{3,4}[a-zA-Z]?)\b', re.IGNORECASE),
            # Galaxy S24, Pixel 7, etc.
            re.compile(r'(?P<base>[a-zA-Z]+)\s+(?P<model>[a-zA-Z]\d{1,2})(\s+(?P<variant>ultra|pro|\+|plus|slim))?', re.IGNORECASE),
            # PlayStation 5
            re.compile(r'playstation\s*(?P<model>\d)(\s+(?P<variant>slim|digital))?', re.IGNORECASE),
            # EliteBook 840 G5
            re.compile(r'(?P<base>[a-zA-Z]+)\s*(?P<model>\d{3})\s*g(?P<generation>\d)', re.IGNORECASE),
            # Surface Pro 8
            re.compile(r'surface\s+pro\s+(?P<model>\d)', re.IGNORECASE),
            # Generic model numbers (like M700Q)
            re.compile(r'\b(?P<model>[a-zA-Z]\d{3,5}[a-zA-Z]?)\b', re.IGNORECASE),
        ]
    
    def _clean_product_name(self, product_name: str) -> str:
        """Clean product name by removing prefixes and normalizing whitespace."""
        # Remove prefixes like "Refurbished", "Certified", etc.
        cleaned = re.sub(r'^(?:refurbished|certified|renewed|recertified|rf)\s+', '', product_name, flags=re.IGNORECASE)
        
        # Normalize whitespace
        cleaned = " ".join(cleaned.split())
        
        return cleaned
    
    def extract_product_components(self, product_name: str) -> Dict[str, str]:
        """
        Extract key components from a product name including brand, line, model, etc.
        
        Args:
            product_name: The name of the product to analyze
            
        Returns:
            Dictionary with extracted components
        """
        # Clean product name
        cleaned_name = self._clean_product_name(product_name)
        
        components = {
            'original_name': product_name,
            'cleaned_name': cleaned_name,
            'brand': None,
            'product_line': None,
            'model_number': None,
            'series': None,
            'variant': None,
            'form_factor': None,
            'family_key_parts': [],
        }
        
        # Extract brand
        for brand, pattern in self.brand_patterns.items():
            if pattern.search(cleaned_name):
                components['brand'] = brand
                components['family_key_parts'].append(brand)
                break
        
        # Extract product line
        for line, pattern in self.product_line_patterns.items():
            if pattern.search(cleaned_name):
                components['product_line'] = line
                components['family_key_parts'].append(line)
                break
        
        # Extract series if possible
        for series_name, pattern in self.series_patterns.items():
            if pattern.search(cleaned_name):
                components['series'] = series_name
                # Don't add to family_key_parts as it might be redundant with model extraction
                break
        
        # Extract model number(s)
        model_matches = []
        for pattern in self.model_number_patterns:
            matches = pattern.finditer(cleaned_name)
            for match in matches:
                match_dict = match.groupdict()
                if match_dict.get('model'):
                    # If we have a base (e.g. "thinkpad") and a model (e.g. "t490"), combine them
                    if match_dict.get('base') and not components.get('product_line'):
                        base = match_dict['base'].lower()
                        # Only use the base if it's not a brand (avoid duplication)
                        if base not in [b.lower() for b in self.BRANDS]:
                            components['product_line'] = base
                            components['family_key_parts'].append(base)
                    
                    model = match_dict['model']
                    components['model_number'] = model
                    components['family_key_parts'].append(model)
                    
                    # If there's a variant like "ultra", "pro", "slim", etc.
                    if match_dict.get('variant'):
                        components['variant'] = match_dict['variant']
                        components['family_key_parts'].append(match_dict['variant'])
                    
                    model_matches.append(match_dict)
        
        # Extract form factor
        for factor, pattern in self.form_factor_patterns.items():
            if pattern.search(cleaned_name):
                components['form_factor'] = factor
                break
        
        return components
    
    def generate_family_name(self, components: Dict[str, str]) -> str:
        """Generate a standardized family name from extracted components."""
        if not components['family_key_parts']:
            return None
        
        # Create a family name from the key parts
        parts = []
        
        # Brand is the first part if available
        if components['brand']:
            parts.append(string.capwords(components['brand']))
        
        # Product line comes next
        if components['product_line']:
            parts.append(string.capwords(components['product_line']))
        
        # Model number is essential
        if components['model_number']:
            # Don't capitalize model numbers that are alphanumeric (e.g., T490, A54)
            parts.append(components['model_number'].upper())
        
        # Add variant if available
        if components['variant']:
            parts.append(string.capwords(components['variant']))
        
        # If we only have a model number without context, don't create a family
        if len(parts) <= 1 and components['model_number'] and not (components['brand'] or components['product_line']):
            return None
            
        return " ".join(parts)
    
    def classify_product(self, product_name: str) -> Optional[Tuple[str, float, Dict]]:
        """
        Classify a product and determine its family with confidence score.
        
        Args:
            product_name: The name of the product to classify
            
        Returns:
            Tuple of (family_name, confidence_score, components) or None if no match
        """
        components = self.extract_product_components(product_name)
        family_name = self.generate_family_name(components)
        
        if not family_name:
            return None
            
        # Calculate confidence based on the quality of extracted components
        confidence = 0.5  # Base confidence
        
        # Having all three of brand, product line, and model number is ideal
        if components['brand'] and components['product_line'] and components['model_number']:
            confidence = 0.95
        # Brand + model number is pretty good
        elif components['brand'] and components['model_number']:
            confidence = 0.85
        # Product line + model number is also good
        elif components['product_line'] and components['model_number']:
            confidence = 0.8
        # Just model number is less confident
        elif components['model_number']:
            confidence = 0.7
        # Just brand or product line is very low confidence
        elif components['brand'] or components['product_line']:
            confidence = 0.6
            
        return family_name, confidence, components
    
    def find_similar_family(self, name: str, existing_families: Dict[str, ProductFamily], 
                           threshold: float = 0.8) -> Optional[ProductFamily]:
        """Find a similar existing family using string similarity."""
        if not existing_families:
            return None
            
        name_lower = name.lower()
        best_match = None
        best_ratio = 0
        
        for family_name, family in existing_families.items():
            # Check if the key components match
            ratio = difflib.SequenceMatcher(None, name_lower, family_name.lower()).ratio()
            if ratio > threshold and ratio > best_ratio:
                best_match = family
                best_ratio = ratio
                
        return best_match
    
    def assign_product_families(self, auto_create=True, confidence_threshold=0.7, similarity_threshold=0.8):
        """
        Process products in the database and assign them to product families.
        
        Args:
            auto_create: Whether to automatically create new product families
            confidence_threshold: Minimum confidence score to auto-assign
            similarity_threshold: Threshold for considering families similar
        
        Returns:
            Dict with statistics about the process
        """
        stats = {
            'processed': 0,
            'assigned': 0,
            'skipped': 0,
            'new_families': 0,
            'needs_review': 0,
            'similar_families': 0
        }
        
        # Get products without families
        products_without_family = Product.objects.filter(family__isnull=True)
        stats['processed'] = products_without_family.count()
        
        # Get existing families for lookup
        existing_families = {f.name.lower(): f for f in ProductFamily.objects.all()}
        
        # Dictionary to collect products by family
        family_products = defaultdict(list)
        needs_review = []
        
        # Classify each product
        for product in products_without_family:
            result = self.classify_product(product.name)
            
            if not result:
                stats['skipped'] += 1
                continue
                
            family_name, confidence, components = result
            
            if confidence < confidence_threshold:
                # Add to review list
                needs_review.append((product, family_name, confidence, components))
                stats['needs_review'] += 1
                continue
                
            # Try to find the family by exact match
            family_key = family_name.lower()
            if family_key in existing_families:
                # Add to family group for later assignment
                family_products[family_name].append((product, confidence, existing_families[family_key]))
            else:
                # Try to find a similar family
                similar_family = self.find_similar_family(family_name, existing_families, similarity_threshold)
                
                if similar_family:
                    # Add to the similar family
                    family_products[similar_family.name].append((product, confidence, similar_family))
                    stats['similar_families'] += 1
                elif auto_create:
                    # Create a new family
                    new_family = ProductFamily.objects.create(
                        name=family_name,
                        description=f"Auto-created family for {family_name} products"
                    )
                    existing_families[family_key] = new_family
                    family_products[family_name].append((product, confidence, new_family))
                    stats['new_families'] += 1
                else:
                    # Add to review list if not auto-creating
                    needs_review.append((product, family_name, confidence, components))
                    stats['needs_review'] += 1
        
        # Assign products to families
        for family_name, products_data in family_products.items():
            for product, confidence, family in products_data:
                product.family = family
                product.save(update_fields=['family'])
                stats['assigned'] += 1
        
        return stats, needs_review

def apply_smart_family_classification(auto_create=True, confidence_threshold=0.7, similarity_threshold=0.8):
    """
    Apply the smart product family classification to all products without a family.
    
    Args:
        auto_create: Whether to automatically create new product families
        confidence_threshold: Minimum confidence score to auto-assign
        similarity_threshold: Threshold for considering families similar
    
    Returns:
        Tuple of (stats, needs_review)
    """
    classifier = SmartProductFamilyClassifier()
    stats, needs_review = classifier.assign_product_families(
        auto_create=auto_create,
        confidence_threshold=confidence_threshold,
        similarity_threshold=similarity_threshold
    )
    
    # Log information about the classification
    logger.info(f"Smart product family classification complete: {stats}")
    if needs_review:
        logger.info(f"{len(needs_review)} products need manual review for family assignment")
        
    return stats, needs_review