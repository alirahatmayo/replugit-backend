import os
import sys
from pathlib import Path

def list_files_and_directories(root_dir, output_file=None):
    """
    Lists all files and directories in the given root directory recursively.
    
    Args:
        root_dir (str): The root directory to start listing from
        output_file (str, optional): Path to file where output should be written
    """
    # Convert to absolute path if not already
    root_dir = os.path.abspath(root_dir)
    
    if output_file:
        output_stream = open(output_file, 'w', encoding='utf-8')
    else:
        output_stream = sys.stdout
    
    print(f"Project structure for: {root_dir}", file=output_stream)
    print("-" * 80, file=output_stream)
    
    # Track folders with models.py files
    models_files = []
    
    for root, dirs, files in os.walk(root_dir):
        # Calculate the level to determine indentation
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        
        # Print current directory
        folder_name = os.path.basename(root)
        print(f"{indent}{folder_name}/", file=output_stream)
        
        # Check if this folder has a models.py file
        if 'models.py' in files:
            models_files.append(os.path.join(root, 'models.py'))
        
        # Print all files
        sub_indent = ' ' * 4 * (level + 1)
        for file in sorted(files):
            print(f"{sub_indent}{file}", file=output_stream)
    
    # Print section with model files
    if models_files:
        print("\n\nDjango Models Found:", file=output_stream)
        print("-" * 80, file=output_stream)
        
        for model_file in sorted(models_files):
            rel_path = os.path.relpath(model_file, root_dir)
            print(f"- {rel_path}", file=output_stream)
            
            # Optionally, you could parse and list the actual model classes here
            # This would require more complex code to parse Python files
    
    if output_file:
        output_stream.close()
        print(f"Project structure written to {output_file}")

if __name__ == "__main__":
    backend_dir = r"d:\replugit\replugit-backend"
    output_file = r"d:\replugit\project_structure.txt"
    
    if not os.path.exists(backend_dir):
        print(f"Error: Directory {backend_dir} does not exist!")
        sys.exit(1)
        
    list_files_and_directories(backend_dir, output_file)
    print(f"\nRun this script with: python list_project_structure.py")