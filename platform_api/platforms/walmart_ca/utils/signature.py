import os
import subprocess
from typing import Tuple
from django.conf import settings

def generate_signature(url: str, method: str, client_id: str, private_key: str) -> Tuple[str, str]:
    """Generate digital signature for Walmart CA API"""
    jar_path = os.path.join(settings.BASE_DIR, "platform_api/platforms/walmart_ca/utils/DigitalSignatureUtil-1.0.0.jar")
    temp_file = os.path.join(settings.BASE_DIR, "platform_api/platforms/walmart_ca/temp/temp_signature.txt")
    
    # Ensure temp directory exists
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)
    
    try:
        # Run Java utility
        result = subprocess.run([
            "java",
            "-jar",
            jar_path,
            "DigitalSignatureUtil",
            url,
            client_id,
            private_key,
            method.upper(),
            temp_file
        ], capture_output=True, text=True, check=True)
        
        # Read signature from temp file
        with open(temp_file, 'r') as f:
            lines = f.readlines()
            signature = lines[0].split(':')[1].strip()
            timestamp = lines[1].split(':')[1].strip()
            return signature, timestamp
            
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Signature generation failed: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)