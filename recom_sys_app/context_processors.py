"""
Context processors for recom_sys_app.
These make variables available to all templates.
"""

from django.conf import settings


def websocket_settings(request):
    """
    Provides WebSocket configuration to templates.

    If WEBSOCKET_HOST is set, WebSockets will connect directly to that host
    (useful when CloudFront doesn't proxy WebSockets properly).
    Otherwise, WebSockets connect to the same host as the page.
    """
    websocket_host = getattr(settings, "WEBSOCKET_HOST", "")
    production_domain = getattr(settings, "PRODUCTION_DOMAIN", "")
    cloudfront_domain = getattr(settings, "CLOUDFRONT_DOMAIN", "")
    use_https = getattr(settings, "USE_HTTPS", False)

    # For media files: Use S3 if configured, otherwise CloudFront/EB
    # S3 is the best solution - it provides HTTPS and scalability
    aws_bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

    if aws_bucket:
        # Using S3 - media URLs are already absolute S3 URLs
        # No need to override, Django will generate correct S3 URLs
        media_host = ""
        media_protocol = "https"
    else:
        # Fallback: Use CloudFront or EB domain
        media_host = ""
        media_protocol = "https" if (request.is_secure() or use_https) else "http"
        host = request.get_host()

        if cloudfront_domain and cloudfront_domain in host:
            # User is accessing via CloudFront
            # Try to use CloudFront for media (if configured to serve /media/*)
            media_host = host
            media_protocol = "https"
        elif production_domain or websocket_host:
            # Fallback: Use EB domain (will have mixed content if page is HTTPS)
            media_host = production_domain or websocket_host
            media_protocol = "http"  # EB doesn't have SSL

    return {
        "WEBSOCKET_HOST": websocket_host,
        "USE_HTTPS": use_https,
        "MEDIA_HOST": media_host,
        "MEDIA_PROTOCOL": media_protocol,
        "PRODUCTION_DOMAIN": production_domain,
    }
