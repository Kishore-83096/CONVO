import os
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("No container command was provided.")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messenger_config.settings")

    # Docker Compose and Cloud Run inject the complete runtime environment.
    # Cross-service addresses must already use the correct Docker/GCP DNS host.
    # Database migrations are intentionally NOT run here: local Compose uses the
    # one-shot messenger-migrate service and GCP deployments use a migration job.
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
