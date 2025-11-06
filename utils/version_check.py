"""
Version checking utilities for UVV addon
"""
import urllib.request
import urllib.error
import json
import os
import bpy
from .. import __version__

# GitHub repository information
GITHUB_OWNER = "Konzui"
GITHUB_REPO = "UVV"
GITHUB_API_URL_LATEST = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_API_URL_ALL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Note: For private repositories, you need a GitHub Personal Access Token
# Set it as an environment variable: GITHUB_TOKEN
# Or make the repository public to allow unauthenticated access


def fetch_latest_release_info():
    """
    Fetch the latest release information from GitHub Releases API.
    
    Returns:
        tuple: (version_string, download_url) or (None, None) if failed
        version_string: Latest version string (e.g., "0.0.9") without 'v' prefix
        download_url: Direct download URL for the .zip file
    """
    try:
        # Try to get the latest non-pre-release first
        print(f"UVV: Fetching latest release from GitHub API: {GITHUB_API_URL_LATEST}")
        
        # Create request with timeout
        request = urllib.request.Request(GITHUB_API_URL_LATEST)
        request.add_header('User-Agent', 'UVV-Addon/1.0')
        request.add_header('Accept', 'application/vnd.github.v3+json')
        
        # Add authentication token if available (for private repositories)
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            request.add_header('Authorization', f'token {github_token}')
            print("UVV: Using GitHub token for authentication")
        
        # Fetch the release info with 10 second timeout
        print("UVV: Opening URL connection...")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                print(f"UVV: HTTP Response Code: {response.getcode()}")
                
                if response.getcode() != 200:
                    print(f"UVV: Unexpected HTTP status code: {response.getcode()}")
                    return None, None
                
                # Parse JSON response
                data = json.loads(response.read().decode('utf-8'))
                
                # Extract version from tag_name (remove 'v' prefix if present)
                tag_name = data.get('tag_name', '')
                # Handle both 'v0.1.0' and 'v.0.1.0' formats
                if tag_name.startswith('v.'):
                    version = tag_name[2:]  # Remove 'v.' prefix
                elif tag_name.startswith('v'):
                    version = tag_name[1:]  # Remove 'v' prefix
                else:
                    version = tag_name
                
                print(f"UVV: Found latest release version: {version}")
                
                # Find the .zip asset
                assets = data.get('assets', [])
                download_url = None
                
                for asset in assets:
                    if asset.get('name', '').endswith('.zip'):
                        download_url = asset.get('browser_download_url')
                        print(f"UVV: Found download URL: {download_url}")
                        break
                
                if not download_url:
                    print("UVV: Warning: No .zip asset found in release")
                    return version, None
                
                return version, download_url
        except urllib.error.HTTPError as e:
            # If 404, it might be because only pre-releases exist
            # Try fetching all releases and get the latest one (including pre-releases)
            if e.code == 404:
                print("UVV: No regular releases found, checking for pre-releases...")
                return _fetch_latest_from_all_releases(github_token)
            else:
                raise  # Re-raise if it's not a 404
            
    except urllib.error.URLError as e:
        print(f"UVV: Network error checking for updates: {e}")
        print(f"UVV: Error type: {type(e).__name__}")
        return None, None
    except urllib.error.HTTPError as e:
        print(f"UVV: HTTP error checking for updates: {e}")
        print(f"UVV: HTTP status code: {e.code}")
        print(f"UVV: HTTP reason: {e.reason}")
        
        if e.code == 404:
            print("UVV: No published releases found. Make sure:")
            print("  1. The release is published (not a draft)")
            print("  2. The release is NOT set as 'pre-release' (uncheck pre-release checkbox)")
            print("  3. The release has at least one asset (.zip file) attached")
            print("  4. The repository is public")
            print("")
            print("Note: Pre-releases are excluded from /latest endpoint.")
            print("      Either uncheck 'pre-release' or create a regular release.")
        
        return None, None
    except json.JSONDecodeError as e:
        print(f"UVV: JSON decode error: {e}")
        return None, None
    except Exception as e:
        print(f"UVV: Error checking for updates: {e}")
        print(f"UVV: Error type: {type(e).__name__}")
        import traceback
        print("UVV: Full traceback:")
        traceback.print_exc()
        return None, None


def _fetch_latest_from_all_releases(github_token=None):
    """
    Fetch the latest release from all releases (including pre-releases).
    Used as fallback when /latest returns 404.
    
    Args:
        github_token: Optional GitHub token for authentication
        
    Returns:
        tuple: (version_string, download_url) or (None, None) if failed
    """
    try:
        print(f"UVV: Fetching all releases from GitHub API: {GITHUB_API_URL_ALL}")
        
        request = urllib.request.Request(GITHUB_API_URL_ALL)
        request.add_header('User-Agent', 'UVV-Addon/1.0')
        request.add_header('Accept', 'application/vnd.github.v3+json')
        
        if github_token:
            request.add_header('Authorization', f'token {github_token}')
        
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.getcode() != 200:
                return None, None
            
            releases = json.loads(response.read().decode('utf-8'))
            
            if not releases:
                print("UVV: No releases found in repository")
                return None, None
            
            # Get the first release (they're sorted by creation date, newest first)
            latest_release = releases[0]
            
            # Extract version
            tag_name = latest_release.get('tag_name', '')
            if tag_name.startswith('v.'):
                version = tag_name[2:]
            elif tag_name.startswith('v'):
                version = tag_name[1:]
            else:
                version = tag_name
            
            print(f"UVV: Found latest release version: {version} (pre-release: {latest_release.get('prerelease', False)})")
            
            # Find the .zip asset
            assets = latest_release.get('assets', [])
            download_url = None
            
            for asset in assets:
                if asset.get('name', '').endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    print(f"UVV: Found download URL: {download_url}")
                    break
            
            if not download_url:
                print("UVV: Warning: No .zip asset found in release")
                return version, None
            
            return version, download_url
            
    except Exception as e:
        print(f"UVV: Error fetching all releases: {e}")
        return None, None


def fetch_latest_version():
    """
    Fetch the latest version from GitHub Releases API.
    
    Returns:
        str: Latest version string (e.g., "0.0.9") or None if failed
    """
    version, _ = fetch_latest_release_info()
    return version


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
        
        # Fetch latest version and download URL
        latest_version, download_url = fetch_latest_release_info()
        
        if latest_version:
            # Compare with current version
            current_version = __version__
            is_newer = compare_versions(current_version, latest_version)
            
            if is_newer:
                settings.latest_version_available = latest_version
                # Store download URL for install operator
                if hasattr(settings, 'update_download_url'):
                    settings.update_download_url = download_url or ""
                print(f"UVV: New version {latest_version} available (current: {current_version})")
                if download_url:
                    print(f"UVV: Download URL: {download_url}")
            else:
                settings.latest_version_available = ""
                if hasattr(settings, 'update_download_url'):
                    settings.update_download_url = ""
                print(f"UVV: Up to date (current: {current_version}, latest: {latest_version})")
        else:
            settings.latest_version_available = ""
            if hasattr(settings, 'update_download_url'):
                settings.update_download_url = ""
            print("UVV: Could not fetch latest version")
            
        return True
        
    except Exception as e:
        print(f"UVV: Error during version check: {e}")
        settings.latest_version_available = ""
        if hasattr(settings, 'update_download_url'):
            settings.update_download_url = ""
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
    Debug function to test GitHub API fetching manually.
    Call this from Blender's Python console to debug issues.
    """
    print("=" * 60)
    print("UVV: DEBUG - Manual GitHub API fetch test")
    print("=" * 60)
    
    version, url = fetch_latest_release_info()
    
    print("=" * 60)
    print(f"UVV: DEBUG - Version: {version}")
    print(f"UVV: DEBUG - Download URL: {url}")
    print("=" * 60)
    
    return version, url
