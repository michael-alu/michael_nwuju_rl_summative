"""
Watch an agent run the ThinBook Pension fund in the browser (three.js), with one line per day in this terminal.

Starts the server, loads the best trained agent, opens the browser and plays a game at 5x speed.

Run from the project root:

uv run play.py
uv run play.py --player random --seed 100042 --speed 20
uv run play.py --no-browser --port 8001
"""

import sys

from environment.rendering import play_main


def main() -> None:
    play_main(sys.argv[1:])


if __name__ == "__main__":
    main()
