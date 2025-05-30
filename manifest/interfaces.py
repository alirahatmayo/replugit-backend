
  0 ;OPOP f0rom abc import ABC, abstractmethod
)_p \OLs898008890 s ManifestProcessorInterface(ABC):
    """
    Interface for manifest processors.
    
    Different manifest formats can implement this interface to provide
    specialized processing for different product types (computers, phones, etc).
    """
    
    @abstractmethod
    def extract_product_info(self, manifest_item):
        """
        Extract product information from a manifest item
        
        Args:
            manifest_item: The ManifestItem instance
            
        Returns:
            dict: Dictionary containing normalized product information
        """
        pass
        
    @abstractmethod
    def determine_condition(self, manifest_item):
        """
        Determine the condition of the product from manifest data
        
        Args:
            manifest_item: The ManifestItem instance
            
        Returns:
            str: Condition grade (A, B, C, D)
            str: Condition notes
        """
        pass
        
    @abstractmethod
    def requires_qc(self, manifest_item):
        """
        Determine if the item requires quality control
        
        Args:
            manifest_item: The ManifestItem instance
            
        Returns:
            bool: True if QC is required, False otherwise
        """
        pass
        
    @abstractmethod
    def get_group_fields(self):
        """
        Get the fields to use for grouping similar items
        
        Returns:
            list: List of field names
        """
        pass


class ComputerEquipmentProcessor(ManifestProcessorInterface):
    """
    Specialized processor for computer equipment manifest data.
    
    Handles the format in the example manifest with fields like:
    - BARCODE, SERIAL, OEM, MODEL, PROCESSOR, MEMORY, HDD, etc.
    """
    
    def extract_product_info(self, manifest_item):
        data = {}
        raw = manifest_item.raw_data
        
        # Extract basic product info with fallbacks for different column names
        data['manufacturer'] = self._get_value(raw, ['OEM', 'MANUFACTURER', 'MAKE', 'BRAND'])
        data['model'] = self._get_value(raw, ['MODEL'])
        data['serial'] = self._get_value(raw, ['SERIAL', 'SERIAL NUMBER', 'SN'])
        data['barcode'] = self._get_value(raw, ['BARCODE', 'BARCODE/ID', 'ID'])
        
        # Extract and normalize specifications
        data['processor'] = self._get_value(raw, ['PROCESSOR', 'CPU', 'PROCESSOR TYPE'])
        data['memory'] = self._normalize_memory(self._get_value(raw, ['MEMORY', 'RAM']))
        data['storage'] = self._normalize_storage(self._get_value(raw, ['HDD', 'STORAGE', 'DISK']))
        data['battery'] = self._normalize_battery(self._get_value(raw, ['BATTERY']))
        
        # Extract pricing
        data['price'] = self._normalize_price(self._get_value(raw, ['PRICE USD', 'PRICE', 'UNIT PRICE']))
        
        return data
        
    def determine_condition(self, manifest_item):
        raw = manifest_item.raw_data
        
        # Get condition grade with fallbacks
        grade = self._get_value(raw, ['GRADE', 'CONDITION', 'CONDITION GRADE'])
        if not grade:
            grade = 'B'  # Default to B grade if not specified
            
        # Get condition notes
        notes = self._get_value(raw, ['OTHER DETAILS', 'COMMENTS', 'NOTES'])
        
        return grade, notes
        
    def requires_qc(self, manifest_item):
        """Determine if item requires QC based on condition and other factors"""
        grade, notes = self.determine_condition(manifest_item)
        
        # Items with condition worse than A need QC
        if grade and grade.upper() != 'A':
            return True
            
        # Items with certain keywords in notes need QC
        if notes and any(kw in notes.lower() for kw in ['broken', 'damage', 'crack', 'missing', 'fail']):
            return True
            
        return False
        
    def get_group_fields(self):
        """Get fields for grouping similar computer items"""
        return ['manufacturer', 'model', 'processor', 'memory', 'storage', 'condition_grade']
        
    def _get_value(self, data, possible_keys):
        """Try multiple possible keys and return the first value found"""
        for key in possible_keys:
            for data_key in data.keys():
                if data_key.upper() == key.upper() and data[data_key]:
                    return data[data_key]
        return None
        
    def _normalize_memory(self, memory_str):
        """Normalize memory specification to a standard format"""
        if not memory_str:
            return None
            
        memory_str = str(memory_str).upper()
        if 'GB' in memory_str:
            try:
                value = float(memory_str.replace('GB', '').strip())
                return f"{int(value) if value.is_integer() else value} GB"
            except (ValueError, AttributeError):
                pass
                
        return memory_str
        
    def _normalize_storage(self, storage_str):
        """Normalize storage specification to a standard format"""
        if not storage_str:
            return None
            
        if isinstance(storage_str, str):
            storage_str = storage_str.upper()
            
            # Handle TB values
            if 'TB' in storage_str:
                try:
                    value = float(storage_str.replace('TB', '').strip())
                    # Convert to GB for consistency
                    return f"{int(value * 1024) if (value * 1024).is_integer() else value * 1024} GB"
                except (ValueError, AttributeError):
                    pass
                    
            # Handle GB values
            if 'GB' in storage_str:
                try:
                    value = float(storage_str.replace('GB', '').strip())
                    return f"{int(value) if value.is_integer() else value} GB"
                except (ValueError, AttributeError):
                    pass
                    
            # Handle special values
            if storage_str in ['N/A', 'NA', '']:
                return None
                
        return storage_str
        
    def _normalize_battery(self, battery_str):
        """Normalize battery status to boolean"""
        if not battery_str:
            return False
            
        if isinstance(battery_str, bool):
            return battery_str
            
        battery_str = str(battery_str).upper()
        return battery_str in ['Y', 'YES', 'TRUE']
        
    def _normalize_price(self, price_str):
        """Normalize price to decimal value"""
        if not price_str:
            return None
            
        if isinstance(price_str, (int, float)):
            return price_str
            
        # Remove currency symbols and commas
        if isinstance(price_str, str):
            price_str = price_str.replace('$', '').replace(',', '')
            try:
                return float(price_str)
            except ValueError:
                pass
                
        return None
