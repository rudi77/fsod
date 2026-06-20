"""Erlaubt `python -m agentkit` als Einstieg in die CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
