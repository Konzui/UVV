"""
Version checking utilities for UVV addon
"""
import urllib.request
import urllib.error
import re
import bpy
from .. import __version__


def fetch_latest_version():
    """
    Fetch the latest version from the download page by parsing CMS-bound text elements.
    
    Returns:
        str: Latest version string (e.g., "5.2.0") or None if failed
    """
    url = "https://uvv.framer.website/downloads"
    
    try:
        print(f"UVV: Fetching page to find CMS-bound version text: {url}")
        
        # Create request with timeout
        request = urllib.request.Request(url)
        request.add_header('User-Agent', 'UVV-Addon/1.0')
        print("UVV: Request headers set")
        
        # Fetch the page with 5 second timeout
        print("UVV: Opening URL connection...")
        with urllib.request.urlopen(request, timeout=5) as response:
            print(f"UVV: HTTP Response Code: {response.getcode()}")
            print(f"UVV: Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"UVV: Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
            
            html_content = response.read().decode('utf-8')
            print(f"UVV: HTML content length: {len(html_content)} characters")
            
        # Look for version in the page title
        print("UVV: Searching for version in page title...")
        
        # Parse the page title for version information
        title_pattern = r'<title[^>]*>([^<]+)</title>'
        title_match = re.search(title_pattern, html_content, re.IGNORECASE)
        
        if title_match:
            title = title_match.group(1).strip()
            print(f"UVV: Found page title: {title}")
            
            # Look for version pattern in title (e.g., "UVV v0.0.1 | Downloads")
            version_pattern = r'v([0-9]+\.[0-9]+\.[0-9]+)'
            version_match = re.search(version_pattern, title)
            
            if version_match:
                version = version_match.group(1)
                print(f"UVV: Found version in title: {version}")
                return version
            else:
                print("UVV: No version found in title")
        else:
            print("UVV: No title tag found")
        
        print("UVV: No version information found in page title")
        return None
            
    except urllib.error.URLError as e:
        print(f"UVV: Network error checking for updates: {e}")
        print(f"UVV: Error type: {type(e).__name__}")
        return None
    except urllib.error.HTTPError as e:
        print(f"UVV: HTTP error checking for updates: {e}")
        print(f"UVV: HTTP status code: {e.code}")
        print(f"UVV: HTTP reason: {e.reason}")
        return None
    except Exception as e:
        print(f"UVV: Error checking for updates: {e}")
        print(f"UVV: Error type: {type(e).__name__}")
        import traceback
        print("UVV: Full traceback:")
        traceback.print_exc()
        return None


def compare_versions(current, latest):
    """
    Compare two version strings using semantic versioning.
    
    Args:
        current (str): Current version (e.g., "5.1.0")
        latest (str): Latest version (e.g., "5.2.0")
        
    Returns:
        bool: True if latest is newer than current
    """
    if not current or not latest:
        return False
        
    try:
        # Split version strings and convert to integers
        current_parts = [int(x) for x in current.split('.')]
        latest_parts = [int(x) for x in latest.split('.')]
        
        # Pad with zeros to ensure same length
        max_len = max(len(current_parts), len(latest_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        
        # Compare each segment
        for current_part, latest_part in zip(current_parts, latest_parts):
            if latest_part > current_part:
                return True
            elif latest_part < current_part:
                return False
                
        return False  # Versions are equal
        
    except (ValueError, AttributeError) as e:
        print(f"UVV: Error comparing versions '{current}' and '{latest}': {e}")
        return False


def check_for_updates(context):
    """
    Main function to check for updates and update the UI properties.
    
    Args:
        context: Blender context
        
    Returns:
        bool: True if update check completed successfully
    """
    if not context or not hasattr(context.scene, 'uvv_settings'):
        print("UVV: No valid context for version check")
        return False
        
    settings = context.scene.uvv_settings
    
    # Prevent multiple simultaneous checks
    if settings.version_check_in_progress:
        print("UVV: Version check already in progress")
        return False
        
    settings.version_check_in_progress = True
    
    try:
        print("UVV: Checking for updates...")
        
        # Fetch latest version
        latest_version = fetch_latest_version()
        
        if latest_version:
            # Compare with current version
            current_version = __version__
            is_newer = compare_versions(current_version, latest_version)
            
            if is_newer:
                settings.latest_version_available = latest_version
                print(f"UVV: New version {latest_version} available (current: {current_version})")
            else:
                settings.latest_version_available = ""
                print(f"UVV: Up to date (current: {current_version}, latest: {latest_version})")
        else:
            settings.latest_version_available = ""
            print("UVV: Could not fetch latest version")
            
        return True
        
    except Exception as e:
        print(f"UVV: Error during version check: {e}")
        settings.latest_version_available = ""
        return False
        
    finally:
        settings.version_check_in_progress = False


def auto_check_for_updates():
    """
    Timer function for automatic version checking on addon load.
    This function is called by bpy.app.timers.register()
    """
    try:
        context = bpy.context
        if context and hasattr(context.scene, 'uvv_settings'):
            check_for_updates(context)
    except Exception as e:
        print(f"UVV: Error in auto version check: {e}")
    
    # Return None to stop the timer (run once)
    return None


def debug_website_fetch():
    """
    Debug function to test website fetching manually.
    Call this from Blender's Python console to debug issues.
    """
    print("=" * 60)
    print("UVV: DEBUG - Manual website fetch test")
    print("=" * 60)
    
    result = fetch_latest_version()
    
    print("=" * 60)
    print(f"UVV: DEBUG - Final result: {result}")
    print("=" * 60)
    
    return result
