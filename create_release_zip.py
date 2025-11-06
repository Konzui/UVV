"""
Helper script to create a clean zip file for GitHub releases.
Excludes development files like CLAUDE.md and .claude/ folder.

Usage:
    python create_release_zip.py [version]
    
Example:
    python create_release_zip.py 0.0.9

Note: Run this script from outside the addon directory, or ensure Python
doesn't import the addon's modules. The script only uses standard library modules.
"""

import os
import sys

# Get script directory BEFORE any other imports to avoid conflicts
SCRIPT_DIR_STR = os.path.dirname(os.path.abspath(__file__))

# Change to parent directory to avoid importing addon modules
# This prevents Python from finding the addon's 'types' directory
PARENT_DIR = os.path.dirname(SCRIPT_DIR_STR)
os.chdir(PARENT_DIR)

# Remove addon directory from Python path if present
if SCRIPT_DIR_STR in sys.path:
    sys.path.remove(SCRIPT_DIR_STR)

# Now import standard library modules (safe after changing directory)
from pathlib import Path
import zipfile
import shutil

# Convert to Path object and change back to script directory for file operations
SCRIPT_DIR = Path(SCRIPT_DIR_STR)
os.chdir(SCRIPT_DIR)

# Files and folders to exclude from the release zip
EXCLUDE_PATTERNS = [
    'CLAUDE.md',
    '.claude',
    '.git',
    '.gitignore',
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.DS_Store',
    'Thumbs.db',
    'create_release_zip.py',
    'UVV.zip',  # Exclude any existing zip files
]

# SCRIPT_DIR is already defined above
ADDON_NAME = SCRIPT_DIR.name  # Should be "UVV"

def should_exclude(file_path, root_path):
    """Check if a file or folder should be excluded from the zip"""
    rel_path = file_path.relative_to(root_path)
    
    # Check against exclude patterns
    for pattern in EXCLUDE_PATTERNS:
        # Check if it's a direct match
        if pattern in str(rel_path) or pattern in rel_path.name:
            return True
        
        # Check if it's in a folder that matches the pattern
        for part in rel_path.parts:
            if pattern in part:
                return True
    
    # Check for __pycache__ directories
    if '__pycache__' in rel_path.parts:
        return True
    
    # Check for .pyc and .pyo files
    if rel_path.suffix in ['.pyc', '.pyo']:
        return True
    
    return False

def update_version_in_init(version):
    """Update version in __init__.py to match release version"""
    import re
    
    init_file = SCRIPT_DIR / "__init__.py"
    if not init_file.exists():
        print(f"Warning: __init__.py not found at {init_file}")
        return False
    
    try:
        # Read the file
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update __version__ = "x.x.x"
        version_pattern = r'(__version__\s*=\s*["\'])([^"\']+)(["\'])'
        def replace_version(match):
            return match.group(1) + version + match.group(3)
        content = re.sub(version_pattern, replace_version, content)
        
        # Update bl_info['version'] = (x, x, x)
        # Parse version string to tuple: "0.1.2" -> (0, 1, 2)
        version_parts = version.split('.')
        version_tuple = ', '.join(version_parts)  # Just the numbers, no parentheses
        
        # Match bl_info version tuple - capture the parentheses separately
        # Pattern: "version": (0, 1, 2),
        bl_info_pattern = r'("version":\s*\()([^)]+)(\),)'
        def replace_bl_info_version(match):
            return match.group(1) + version_tuple + match.group(3)
        content = re.sub(bl_info_pattern, replace_bl_info_version, content)
        
        # Only write if something changed
        if content != original_content:
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Updated version in __init__.py to {version}")
            return True
        else:
            print(f"Version in __init__.py already matches {version}")
            return True
            
    except Exception as e:
        print(f"Error updating version in __init__.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_release_zip(version=None):
    """Create a clean zip file for GitHub release"""
    
    # If version is provided, automatically update __init__.py
    if version:
        print(f"Updating version in __init__.py to {version}...")
        if not update_version_in_init(version):
            print("Warning: Failed to update version in __init__.py")
            print("You may need to update it manually before creating the release.")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborted.")
                return None
        print()
    
    # Determine output filename
    if version:
        zip_filename = f"{ADDON_NAME}-v{version}.zip"
    else:
        zip_filename = f"{ADDON_NAME}-release.zip"
    
    zip_path = SCRIPT_DIR / zip_filename
    
    # Remove existing zip if it exists
    if zip_path.exists():
        print(f"Removing existing zip: {zip_filename}")
        zip_path.unlink()
    
    print(f"Creating release zip: {zip_filename}")
    print(f"Source directory: {SCRIPT_DIR}")
    print(f"Excluding: {', '.join(EXCLUDE_PATTERNS)}")
    print()
    
    file_count = 0
    total_size = 0
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through all files in the addon directory
        for root, dirs, files in os.walk(SCRIPT_DIR):
            root_path = Path(root)
            
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not should_exclude(root_path / d, SCRIPT_DIR)]
            
            for file in files:
                file_path = root_path / file
                
                # Skip the zip file we're creating
                if file_path == zip_path:
                    continue
                
                # Check if file should be excluded
                if should_exclude(file_path, SCRIPT_DIR):
                    continue
                
                # Calculate relative path for zip
                # IMPORTANT: Blender requires the addon folder to be inside the zip
                # So we need: UVV/__init__.py, not __init__.py at root
                rel_path = file_path.relative_to(SCRIPT_DIR)
                
                # Add the addon folder name as prefix to create proper structure
                # This creates: UVV/__init__.py, UVV/operators/..., etc.
                zip_path_internal = ADDON_NAME / rel_path
                
                # Add file to zip with the folder structure
                zipf.write(file_path, zip_path_internal)
                file_count += 1
                total_size += file_path.stat().st_size
                
                if file_count % 50 == 0:
                    print(f"  Added {file_count} files...", end='\r')
    
    print(f"\n[OK] Created {zip_filename}")
    print(f"  Files: {file_count}")
    print(f"  Size: {total_size / 1024 / 1024:.2f} MB")
    print(f"  Zip size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
    print()
    print(f"Ready to upload to GitHub release!")
    print(f"File location: {zip_path}")
    
    return zip_path

if __name__ == "__main__":
    version = None
    if len(sys.argv) > 1:
        version = sys.argv[1]
        # Remove 'v' prefix if present
        if version.startswith('v'):
            version = version[1:]
    
    try:
        create_release_zip(version)
    except Exception as e:
        print(f"Error creating zip: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

