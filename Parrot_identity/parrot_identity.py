import os
import sys
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def configure_environment() -> str:
    environment = os.getenv("APP_ENV", "").strip().lower()

    # Actual production deployment:
    # Render, GCP or AWS already supplied APP_ENV and all other variables.
    if environment == "production":
        print("Running with production environment variables.")
        return "production"

    # APP_ENV can optionally be set manually for local development.
    if environment == "local":
        load_dotenv(BASE_DIR / ".env.local", override=False)
        print("Loaded .env.local")
        return "local"

    # Interactive selection is allowed only on your local terminal.
    if sys.stdin.isatty():
        selection = input(
            "Select environment [local/production]: "
        ).strip().lower()

        if selection == "local":
            load_dotenv(BASE_DIR / ".env.local", override=False)

        elif selection == "production":
            # Only for testing production settings locally.
            load_dotenv(BASE_DIR / ".env.production", override=False)

        else:
            raise RuntimeError(
                "Enter either 'local' or 'production'."
            )

        loaded_environment = os.getenv("APP_ENV", "").strip().lower()

        if loaded_environment != selection:
            raise RuntimeError(
                f"The selected file must contain APP_ENV={selection}"
            )

        return loaded_environment

    # A deployed process cannot answer input().
    raise RuntimeError(
        "APP_ENV is missing. Set APP_ENV=production "
        "in the deployment environment."
    )


current_environment = configure_environment()


# Import only after the environment is configured.
from app import create_app  # noqa: E402


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=(
            current_environment == "local"
            and os.getenv("FLASK_DEBUG", "0") == "1"
        ),
    )