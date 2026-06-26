import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def command_line_environment() -> str | None:
    parser = argparse.ArgumentParser(
        description="Run the identity service.",
    )
    parser.add_argument(
        "--env",
        choices=("local", "production"),
        help="Load settings from .env.local or .env.production.",
    )
    arguments, _ = parser.parse_known_args()
    return arguments.env


def load_environment_file(environment: str) -> str:
    environment_file = BASE_DIR / f".env.{environment}"

    if not environment_file.is_file():
        raise RuntimeError(
            f"Environment file not found: {environment_file.name}"
        )

    load_dotenv(environment_file, override=True)

    loaded_environment = os.getenv("APP_ENV", "").strip().lower()

    if loaded_environment != environment:
        raise RuntimeError(
            f"{environment_file.name} must contain "
            f"APP_ENV={environment}"
        )

    print(f"Loaded {environment_file.name}")
    return loaded_environment


def configure_environment(selected_environment: str | None = None) -> str:
    if selected_environment:
        return load_environment_file(selected_environment)

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

        if selection not in {"local", "production"}:
            raise RuntimeError(
                "Enter either 'local' or 'production'."
            )

        return load_environment_file(selection)

    # A deployed process cannot answer input().
    raise RuntimeError(
        "APP_ENV is missing. Set APP_ENV=production "
        "in the deployment environment."
    )


current_environment = configure_environment(command_line_environment())


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
