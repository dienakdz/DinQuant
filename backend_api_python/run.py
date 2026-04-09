"""
QuantDinger Python API entrypoint.
"""

import os
import sys

from app import create_app
from app.config.settings import Config

# Ensure UTF-8 console output on Windows to avoid UnicodeEncodeError in logs.
# (PowerShell default encoding may be GBK/CP936.)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Load local .env early so config classes can read from os.environ.
# This keeps local deployment simple: edit one file and run.
try:
    from dotenv import load_dotenv

    this_dir = os.path.dirname(os.path.abspath(__file__))
    # Primary: backend_api_python/.env (same dir as run.py)
    load_dotenv(os.path.join(this_dir, ".env"), override=False)
    # Fallback: repo-root/.env (one level up) for users who place .env at workspace root.
    parent_dir = os.path.dirname(this_dir)
    load_dotenv(os.path.join(parent_dir, ".env"), override=False)
except Exception:
    # python-dotenv is optional; environment variables can still be provided by the OS.
    pass

# Optional: disable tqdm progress bars (some data providers like akshare may emit them),
# keeping console logs clean in local mode.
os.environ.setdefault("TQDM_DISABLE", "1")


# Optional: normalize outbound proxy settings for the whole process.
# This makes requests/yfinance/finnhub/tiingo/GoogleSearch etc work behind a local proxy.
def _apply_proxy_env():
    def _set_if_blank(key: str, value: str) -> None:
        """
        Set env var if it is missing OR present but empty.
        (`os.environ.setdefault` does not override empty strings.)
        """
        cur = os.getenv(key)
        if cur is None or str(cur).strip() == "":
            os.environ[key] = value

    # If user provided explicit proxy URL, honor it.
    proxy_url = (os.getenv("PROXY_URL") or "").strip()

    if not proxy_url:
        return

    # Standard env vars used by requests and many libraries.
    _set_if_blank("ALL_PROXY", proxy_url)
    _set_if_blank("HTTP_PROXY", proxy_url)
    _set_if_blank("HTTPS_PROXY", proxy_url)


_apply_proxy_env()
#################


# Optional: Disable SSL verification for development in corporate environments (SSL Inspection)
# This is NOT recommended for production use.
def _apply_ssl_verify():
    verify_ssl = os.getenv("PYTHON_SSL_VERIFY", "true").lower() == "true"
    if not verify_ssl:
        import requests
        import urllib3
        from urllib3.exceptions import InsecureRequestWarning

        # Suppress InsecureRequestWarning
        urllib3.disable_warnings(InsecureRequestWarning)

        # Monkey patch requests.Session.request to default verify=False
        # This affects requests, yfinance, and many other libraries.
        original_request = requests.Session.request

        def patched_request(self, method, url, *args, **kwargs):
            if "verify" not in kwargs:
                kwargs["verify"] = False
            return original_request(self, method, url, *args, **kwargs)

        requests.Session.request = patched_request

        # Also set common environment variables to skip verification
        os.environ["CURL_CA_BUNDLE"] = ""
        os.environ["REQUESTS_CA_BUNDLE"] = ""
        os.environ["PYTHONHTTPSVERIFY"] = "0"

        print("[DEV ONLY] SSL Verification disabled globally (Corporate SSL Inspection bypass)")


_apply_ssl_verify()

##################

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create app instance (for gunicorn use)
# gunicorn -c gunicorn_config.py "run:app"
app = create_app()


def main():
    """Start application"""
    # Keep startup messages ASCII-only and short.
    print("QuantDinger Python API v2.2.2")

    # ========== Critical Security Check for SECRET_KEY ==========
    # In production (DEBUG=False), the SECRET_KEY MUST NOT use the default example value.
    # This prevents attackers from forging JWT tokens with admin privileges.
    default_secret = "quantdinger-secret-key-change-me"
    current_secret = Config.SECRET_KEY
    if not Config.DEBUG and current_secret == default_secret:
        msg = (
            "\n[SECURITY ERROR] SECRET_KEY is using the default example value.\n"
            "You MUST change SECRET_KEY in backend_api_python/.env before running in production.\n"
            "Example:\n"
            "  SECRET_KEY=$(python - << 'EOF'\n"
            "import secrets; print(secrets.token_hex(32))\n"
            "EOF\n"
        )
        # Print to both stdout and raise to stop the server
        print(msg)
        raise RuntimeError("Insecure SECRET_KEY configuration: using default example value in non-debug mode")

    print(f"Service starting at: http://{Config.HOST}:{Config.PORT}")

    # Flask dev server is for local development only.
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)


if __name__ == "__main__":
    main()
