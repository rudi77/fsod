"""Erlaubt `python -m agentkit` als Alias für die CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
