"""
Script to check for references to the removed ManifestGroupFamilyMapping model
"""
import os
import re
import sys
from pathlib import Path

def search_for_references(directory, pattern):
    """
    Search for pattern in all python files recursively in the given directory
    """
    print(f"Searching for '{pattern}' in '{directory}'...")
    
    files_with_matches = []
    
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.py'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        content = file.read()
                        if re.search(pattern, content):
                            files_with_matches.append(filepath)
                except Exception as e:
                    print(f"Error reading file {filepath}: {str(e)}")
    
    return files_with_matches

def main():
    # Get the root directory of the project
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Patterns to search for
    patterns = [
        r'ManifestGroupFamilyMapping',
        r'family_mappings',
        r'manifest_group_mappings'
    ]
    
    print(f"Checking for references to the removed ManifestGroupFamilyMapping model in {project_root}")
    print("=" * 80)
    
    total_files = 0
    
    for pattern in patterns:
        matches = search_for_references(project_root, pattern)
        if matches:
            print(f"\nFound {len(matches)} files containing '{pattern}':")
            for filepath in matches:
                rel_path = os.path.relpath(filepath, project_root)
                print(f"  - {rel_path}")
            total_files += len(matches)
        else:
            print(f"\nNo files found containing '{pattern}'")
    
    print("\n" + "=" * 80)
    if total_files > 0:
        print(f"Found {total_files} file(s) with potential references to the removed model.")
        print("These files may need to be updated to work with the refactored model.")
    else:
        print("No references to the removed model were found. All clear!")
    
    return 0 if total_files == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
