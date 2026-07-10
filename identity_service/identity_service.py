import os

from app import create_app


current_environment = os.getenv("APP_ENV", "local").strip().lower()
if current_environment not in {"local", "production"}:
    raise RuntimeError(
        "APP_ENV must be 'local' or 'production'. Docker/Cloud deployment must "
        "inject the complete runtime environment."
    )

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", os.getenv("PORT", "5000"))),
        debug=(
            current_environment == "local"
            and os.getenv("FLASK_DEBUG", "0") == "1"
        ),
    )
