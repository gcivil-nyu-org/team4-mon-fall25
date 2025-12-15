# recom_sys_app/geolocation.py
"""
IP-based geolocation utility for detecting user's country.
Used to filter movies by regional availability.
"""
import requests
from django.core.cache import cache


# ISO 3166-1 alpha-2 country codes supported by TMDB watch providers
SUPPORTED_REGIONS = {
    "US",
    "GB",
    "CA",
    "AU",
    "DE",
    "FR",
    "ES",
    "IT",
    "JP",
    "KR",
    "BR",
    "MX",
    "IN",
    "NL",
    "SE",
    "NO",
    "DK",
    "FI",
    "PL",
    "RU",
    "AR",
    "CL",
    "CO",
    "PE",
    "AT",
    "CH",
    "BE",
    "PT",
    "IE",
    "NZ",
    "SG",
    "MY",
    "PH",
    "TH",
    "ID",
    "VN",
    "ZA",
    "EG",
    "NG",
    "KE",
}

# Default region if geolocation fails
DEFAULT_REGION = "US"

# Cache timeout for geolocation results (24 hours)
GEO_CACHE_TIMEOUT = 86400


def get_client_ip(request):
    """
    Extract the client's IP address from the request.
    Handles proxy headers (X-Forwarded-For) for load balancers like AWS ELB.

    Args:
        request: Django HttpRequest object

    Returns:
        str: Client IP address
    """
    # Check for forwarded IP (behind load balancer/proxy)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs; first one is the client
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        # Direct connection
        ip = request.META.get("REMOTE_ADDR", "")

    return ip


def get_country_from_ip(ip_address):
    """
    Look up the country code from an IP address using a free geolocation API.
    Results are cached to minimize API calls.

    Args:
        ip_address: String IP address (IPv4 or IPv6)

    Returns:
        str: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "IN")
             Returns DEFAULT_REGION if lookup fails
    """
    # Skip localhost/private IPs
    if ip_address in ("127.0.0.1", "localhost", "", None):
        return DEFAULT_REGION

    if ip_address.startswith(("10.", "172.", "192.168.")):
        return DEFAULT_REGION

    # Check cache first
    cache_key = f"geo_country_{ip_address}"
    cached_country = cache.get(cache_key)
    if cached_country:
        return cached_country

    try:
        # Use ip-api.com (free, no API key required, 45 requests/minute limit)
        response = requests.get(
            f"http://ip-api.com/json/{ip_address}",
            params={"fields": "status,countryCode"},
            timeout=3,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "success":
            country_code = data.get("countryCode", DEFAULT_REGION)

            # Validate it's a supported region
            if country_code not in SUPPORTED_REGIONS:
                country_code = DEFAULT_REGION

            # Cache the result
            cache.set(cache_key, country_code, GEO_CACHE_TIMEOUT)

            return country_code

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"[Geolocation] Error looking up IP {ip_address}: {e}")

    return DEFAULT_REGION


def get_user_region(request):
    """
    Get the user's region/country code from the request.
    This is the main function to use in views.

    Args:
        request: Django HttpRequest object

    Returns:
        str: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "IN")
    """
    # First check if user has a region preference set in session
    session_region = request.session.get("user_region")
    if session_region and session_region in SUPPORTED_REGIONS:
        return session_region

    # Otherwise, detect from IP
    ip = get_client_ip(request)
    region = get_country_from_ip(ip)

    # Store in session for future requests
    request.session["user_region"] = region

    return region


def set_user_region(request, region_code):
    """
    Manually set the user's preferred region (for user override).

    Args:
        request: Django HttpRequest object
        region_code: ISO 3166-1 alpha-2 country code

    Returns:
        bool: True if region was set successfully, False if invalid region
    """
    region_code = region_code.upper()

    if region_code in SUPPORTED_REGIONS:
        request.session["user_region"] = region_code
        return True

    return False


# Region display names for UI
REGION_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "JP": "Japan",
    "KR": "South Korea",
    "BR": "Brazil",
    "MX": "Mexico",
    "IN": "India",
    "NL": "Netherlands",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "PL": "Poland",
    "RU": "Russia",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "PE": "Peru",
    "AT": "Austria",
    "CH": "Switzerland",
    "BE": "Belgium",
    "PT": "Portugal",
    "IE": "Ireland",
    "NZ": "New Zealand",
    "SG": "Singapore",
    "MY": "Malaysia",
    "PH": "Philippines",
    "TH": "Thailand",
    "ID": "Indonesia",
    "VN": "Vietnam",
    "ZA": "South Africa",
    "EG": "Egypt",
    "NG": "Nigeria",
    "KE": "Kenya",
}


def get_all_regions():
    """
    Get all supported regions with their display names.
    Useful for populating a region selector dropdown.

    Returns:
        list: List of dicts with 'code' and 'name' keys, sorted by name
    """
    regions = [{"code": code, "name": name} for code, name in REGION_NAMES.items()]
    return sorted(regions, key=lambda x: x["name"])
