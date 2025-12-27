# kegelpy

[![PyPI - Version](https://img.shields.io/pypi/v/kegelpy.svg)](https://pypi.org/project/kegelpy) [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kegelpy.svg)](https://pypi.org/project/kegelpy) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**kegelpy** is a terminal-based (TUI) Kegel exercise trainer designed to help you strengthen your pelvic floor muscles through progressive, guided workouts. It features a simple, distraction-free interface with visual cues and automatic progress tracking.

## Features

-   **Progressive Difficulty:** Automatically increases difficulty as you advance through levels and days.
-   **Dual Modes:** Combines "Classic" (Hold/Rest) and "Pulse" (Rapid Squeeze/Release) exercises for a complete workout.
-   **Visual Cues:** Clear color-coded indicators (Red for Squeeze, Green for Rest) and progress bars.
-   **Progress Tracking:** Automatically saves your current level and day.
-   **Pause/Resume:** Interrupt your workout if needed without losing progress.
-   **Cross-Platform:** Works on Linux, macOS, and Windows (requires a terminal with `curses` support).

## Installation

### Using pip

```console
pip install kegelpy
```

### Using pipx (Recommended)

For CLI tools, it's often better to use `pipx` to install in an isolated environment:

```console
pipx install kegelpy
```

## Usage

To start the application, simply run:

```console
kegelpy
```

### Navigation

The main menu offers the following options:

-   **[S]tart Workout:** Begin your daily routine.
-   **[I]nfo [How-to]:** Learn how to perform Kegel exercises correctly.
-   **[P]rogress:** View your current level/day and reset progress if needed.
-   **[Q]uit:** Exit the application.

### Controls During Workout

-   **p**: Pause the workout.
-   **s** or **q**: Stop the current session and return to the menu.

## How it Works

1.  **Classic Phase:** You will be prompted to SQUEEZE (hold) and REST for a set duration.
2.  **Pulse Phase:** Rapidly squeeze and release your muscles to build reaction time and control.
3.  **Progression:**
    -   The routine consists of multiple **Levels**.
    -   Each Level has multiple **Days**.
    -   Completing a session advances you to the next Day or Level.
    -   Difficulty increases by adding more reps or longer hold times.

## Data Storage

Your progress is saved locally in a `progress.json` file. The location depends on your operating system:

-   **Linux:** `~/.local/share/kegelpy/` (or `$XDG_DATA_HOME`)
-   **macOS:** `~/Library/Application Support/kegelpy/`
-   **Windows:** `%LOCALAPPDATA%\kegelpy\`

## Development

To set up the project for development:

1.  Clone the repository:
    ```console
    git clone https://github.com/jonnieey/kegelpy.git
    cd kegelpy
    ```

2.  Create a virtual environment and install dependencies (using `hatch` or standard `pip`):
    ```console
    # Using pip
    python -m venv .venv
    source .venv/bin/activate
    pip install -e .
    ```

3.  Run the application:
    ```console
    python -m kegelpy
    ```

## License

`kegelpy` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.