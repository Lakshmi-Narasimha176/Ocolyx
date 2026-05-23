"""Ocolyx entry point."""

from src.ocolyx.app import OcolyxApp


def main() -> None:
    app = OcolyxApp()
    app.run()


if __name__ == "__main__":
    main()
