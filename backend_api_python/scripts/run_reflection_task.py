import os
import sys

from dotenv import load_dotenv

# Add the backend directory to the Python path so app.* can be imported
# The app package lives under backend_api_python/app while this script is under backend_api_python/scripts
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.reflection import ReflectionService


def main():
    # Load backend envs for DATABASE_URL, reflection switches, etc.
    # This script may be run locally, so we must load .env explicitly.
    backend_env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    root_env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(root_env_path):
        load_dotenv(root_env_path, override=False)
    if os.path.exists(backend_env_path):
        load_dotenv(backend_env_path, override=False)

    """
    Run the automated reflection verification task.
    It is intended to run once per day via cron or another task scheduler.
    """
    print("Running Automated Reflection Verification Task...")
    service = ReflectionService()
    stats = service.run_verification_cycle()
    print("Reflection stats:", stats)
    print("Task Completed.")


if __name__ == "__main__":
    main()
