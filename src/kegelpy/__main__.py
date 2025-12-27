"""
Main entry point for running as a module
"""
import sys
import argparse
from kegelpy.kegel import main as main_curses
from kegelpy.kegel_tui import main as main_tui


def main():
    parser = argparse.ArgumentParser(description="KegelPy - Kegel Exercise Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'tui' subcommand
    subparsers.add_parser("tui", help="Launch the Textual TUI version")

    # Parse arguments
    # If no arguments are provided, we default to curses version
    if len(sys.argv) == 1:
        main_curses()
        return

    args = parser.parse_args()

    if args.command == "tui":
        main_tui()
    else:
        # This part might not be reached if argparse handles invalid commands,
        # but just in case:
        main_curses()


if __name__ == "__main__":
    main()
