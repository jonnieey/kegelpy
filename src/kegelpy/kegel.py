#!/usr/bin/env python3
import sys
import os
import curses
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


def get_app_data_file(app_name="kegelpy", filename="progress.json"):
    home = Path.home()

    if sys.platform.startswith("linux"):
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            base_path = Path(xdg_data_home)
        else:
            base_path = home / ".local" / "share"

    elif sys.platform == "win32":
        base_path = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))

    elif sys.platform == "darwin":
        base_path = home / "Library" / "Application Support"

    else:
        base_path = home

    app_dir = base_path / app_name
    app_dir.mkdir(parents=True, exist_ok=True)

    return str(app_dir / filename)


DATA_FILE = get_app_data_file()


@dataclass
class Routine:
    level: int
    day: int
    classic_hold_sec: int
    classic_rest_sec: int
    classic_reps: int
    pulse_reps: int
    total_days_in_level: int


@dataclass
class UserState:
    current_level: int = 1
    current_day: int = 1
    last_performed: str = ""


class LevelGenerator:
    @staticmethod
    def get_days_for_level(level: int) -> int:
        return 4 + (level - 1)

    @staticmethod
    def generate_routine(level: int, day: int) -> Routine:
        base_hold = 3 + ((level - 1) // 5)
        base_rest = 3
        classic_reps = day + (level - 1)
        pulse_reps = 9 + day + ((level - 1) * 2)

        return Routine(
            level=level,
            day=day,
            classic_hold_sec=base_hold,
            classic_rest_sec=base_rest,
            classic_reps=classic_reps,
            pulse_reps=pulse_reps,
            total_days_in_level=LevelGenerator.get_days_for_level(level),
        )


class StateManager:
    def __init__(self, filepath):
        self.filepath = filepath

    def load(self) -> UserState:
        if not os.path.exists(self.filepath):
            return UserState()
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                return UserState(**data)
        except (json.JSONDecodeError, TypeError):
            return UserState()

    def save(self, state: UserState):
        with open(self.filepath, "w") as f:
            json.dump(asdict(state), f, indent=4)

    def advance_progress(
        self, state: UserState, days_in_current_level: int
    ) -> UserState:
        state.last_performed = datetime.now().isoformat()
        if state.current_day >= days_in_current_level:
            state.current_level += 1
            state.current_day = 1
        else:
            state.current_day += 1
        self.save(state)
        return state


class App:
    def __init__(self):
        self.state_manager = StateManager(DATA_FILE)
        self.user_state = self.state_manager.load()
        self.stdscr = None
        self.paused = False
        self.stop_signal = False

        # Colors
        self.COLOR_SQUEEZE = 1
        self.COLOR_REST = 2
        self.COLOR_DEFAULT = 3
        self.COLOR_HEADER = 4

    def center_text(self, text, y_offset=0, color_pair=0):
        """Helper to center text on screen."""
        height, width = self.stdscr.getmaxyx()
        x = max(0, int((width // 2) - (len(text) // 2)))
        y = max(0, int((height // 2) + y_offset))

        # Safety check to prevent crashing if terminal is too small
        if y < height and x < width:
            self.stdscr.addstr(y, x, text, color_pair)

    def draw_header(self):
        self.center_text(
            "=== KEGELPY ===",
            y_offset=-8,
            color_pair=curses.color_pair(4) | curses.A_BOLD,
        )

    def draw_status(self, routine):
        """Draws static status info (Level/Day)."""
        self.center_text(
            f"LEVEL {routine.level} - DAY {routine.day}",
            y_offset=-6,
            color_pair=curses.color_pair(3) | curses.A_BOLD,
        )

    def draw_counters(self, routine, current_classic_rep=None, current_pulse_rep=None):
        """
        Draws only the active counter in decreasing countdown format.
        """

        # --- PULSE PHASE (Active) ---
        if current_pulse_rep is not None:
            remaining = routine.pulse_reps - current_pulse_rep
            pulse_str = f"Pulse Reps: {remaining}/{routine.pulse_reps}"
            self.center_text(pulse_str, y_offset=-4)

        # --- CLASSIC PHASE (Active) ---
        elif current_classic_rep is not None:
            remaining = routine.classic_reps - current_classic_rep
            classic_str = f"Classic Reps: {remaining}/{routine.classic_reps}"
            self.center_text(classic_str, y_offset=-4)

        # --- PRE-START (Show both totals) ---
        else:
            # When exercise hasn't started yet (e.g. countdown screens or pauses before start)
            classic_str = f"Classic Reps: {routine.classic_reps}"
            pulse_str = f"Pulse Reps: {routine.pulse_reps}"
            self.center_text(classic_str, y_offset=-4)
            self.center_text(pulse_str, y_offset=-3)

    def handle_input(self):
        """Non-blocking input check. Returns True if stop requested."""
        try:
            key = self.stdscr.getch()
            if key == ord("p"):
                self.paused = not self.paused
                self.pause_screen()  # Enter blocking pause loop
            elif key == ord("s") or key == ord("q"):
                self.stop_signal = True
                return True
        except curses.error:
            pass
        return False

    def pause_screen(self):
        """Blocking loop for pause state."""
        while self.paused:
            self.stdscr.clear()
            self.draw_header()
            self.center_text(
                "PAUSED", y_offset=0, color_pair=curses.color_pair(3) | curses.A_BLINK
            )
            self.center_text("Press 'p' to Resume", y_offset=2)
            self.stdscr.refresh()

            key = self.stdscr.getch()  # Blocking wait
            if key == ord("p"):
                self.paused = False
            elif key == ord("s") or key == ord("q"):
                self.stop_signal = True
                self.paused = False

    def info_screen(self):
        """Displays instructions for Kegel exercises."""
        while True:
            self.stdscr.clear()
            self.draw_header()

            # Title
            self.center_text(
                "HOW TO KEGEL",
                y_offset=-5,
                color_pair=curses.color_pair(3) | curses.A_BOLD | curses.A_UNDERLINE,
            )

            # Classic Instructions
            self.center_text(
                "1. CLASSIC KEGELS",
                y_offset=-2,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(
                "Identify your pelvic floor muscles (used to stop urine).", y_offset=-1
            )
            self.center_text("SQUEEZE: Tighten these muscles and hold.", y_offset=0)
            self.center_text("REST: Completely relax the muscles.", y_offset=1)

            # Pulse Instructions
            self.center_text(
                "2. PULSE KEGELS",
                y_offset=4,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(
                "Rapidly tighten and relax the pelvic floor muscles.", y_offset=5
            )
            self.center_text(
                "Do not hold. Squeeze then immediately release.", y_offset=6
            )

            # Footer
            self.center_text(
                "Press [q] to Return to Menu",
                y_offset=9,
                color_pair=curses.color_pair(3),
            )

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord("q") or key == ord("Q"):
                break

    def progress_screen(self):
        """Displays current user status and provides a reset option."""
        while True:
            self.stdscr.clear()
            self.draw_header()

            # Display Status Box
            u = self.user_state
            last_date = u.last_performed[:10] if u.last_performed else "Never"

            self.center_text(
                "--- CURRENT PROGRESS ---",
                y_offset=-4,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(f"Level: {u.current_level}", y_offset=-2)
            self.center_text(f"Day: {u.current_day}", y_offset=-1)
            self.center_text(f"Last Workout: {last_date}", y_offset=0)

            # Reset Option
            self.center_text(
                "[R]eset All Progress",
                y_offset=4,
                color_pair=curses.color_pair(1) | curses.A_BOLD,
            )
            self.center_text("[Q]uit to Menu", y_offset=6)

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord("r") or key == ord("R"):
                self.reset_progress()
            elif key == ord("q") or key == ord("Q"):
                break

    def run_timer(self, duration, label, color_idx, routine, current_rep):
        """Runs a countdown timer visually."""
        start_time = time.time()
        time_elapsed = 0

        while time_elapsed < duration:
            if self.handle_input():
                return False
            if self.stop_signal:
                return False

            # Calculate math
            now = time.time()
            time_elapsed = now - start_time
            remaining = max(0.0, duration - time_elapsed)

            # Progress Bar
            bar_len = 40
            filled_len = int((time_elapsed / duration) * bar_len)
            bar = f"[{'=' * filled_len}{'-' * (bar_len - filled_len)}]"

            # Render
            self.stdscr.clear()
            self.draw_header()
            self.draw_status(routine)
            # Pass the current rep so it knows what to display
            self.draw_counters(routine, current_classic_rep=current_rep)

            # Label (SQUEEZE / REST)
            self.center_text(
                label,
                y_offset=0,
                color_pair=curses.color_pair(color_idx) | curses.A_BOLD,
            )

            # Timer Number
            self.center_text(f"{remaining:.1f}s", y_offset=2)

            # Progress Bar
            self.center_text(bar, y_offset=4)

            self.center_text(
                "[p]ause  [s]top", y_offset=8, color_pair=curses.color_pair(3)
            )

            self.stdscr.refresh()
            curses.napms(100)  # Sleep 100ms to reduce CPU usage

        return True

    def run_pulse(self, routine):
        """Runs the rapid pulse phase."""
        for i in range(routine.pulse_reps):
            if self.stop_signal:
                return False

            # Squeeze Phase
            start_sq = time.time()
            while time.time() - start_sq < 0.6:
                if self.handle_input():
                    return False
                self.stdscr.clear()
                self.draw_header()
                self.draw_status(routine)
                # Pass completed Classic reps (so it shows X/X) and current Pulse rep
                self.draw_counters(
                    routine,
                    current_classic_rep=routine.classic_reps - 1,
                    current_pulse_rep=i,
                )

                self.center_text(
                    "SQUEEZE",
                    y_offset=0,
                    color_pair=curses.color_pair(1) | curses.A_BOLD,
                )
                self.stdscr.refresh()
                curses.napms(50)

            # Release Phase
            start_rel = time.time()
            while time.time() - start_rel < 0.6:
                if self.handle_input():
                    return False
                self.stdscr.clear()
                self.draw_header()
                self.draw_status(routine)
                self.draw_counters(
                    routine,
                    current_classic_rep=routine.classic_reps - 1,
                    current_pulse_rep=i,
                )

                self.center_text(
                    "RELEASE",
                    y_offset=0,
                    color_pair=curses.color_pair(2) | curses.A_BOLD,
                )
                self.stdscr.refresh()
                curses.napms(50)

        return True

    def reset_progress(self):
        """Resets user progress after confirmation."""
        while True:
            self.stdscr.clear()
            self.draw_header()

            # Display Status
            u = self.user_state
            self.center_text(
                f"Current Level: {u.current_level} | Day: {u.current_day}", y_offset=-2
            )

            self.center_text(
                "!!! WARNING !!!",
                y_offset=0,
                color_pair=curses.color_pair(1) | curses.A_BOLD,
            )
            self.center_text("Are you sure you want to reset ALL progress?", y_offset=1)
            self.center_text("This action cannot be undone.", y_offset=2)
            self.center_text(
                "[Y]es / [N]o",
                y_offset=4,
                color_pair=curses.color_pair(3) | curses.A_BOLD,
            )

            self.stdscr.refresh()

            key = self.stdscr.getch()

            if key == ord("y") or key == ord("Y"):
                filepath = self.state_manager.filepath
                if os.path.exists(filepath):
                    os.remove(filepath)

                self.user_state = self.state_manager.load()

                self.stdscr.clear()
                self.center_text(
                    "PROGRESS RESET COMPLETE.",
                    y_offset=0,
                    color_pair=curses.color_pair(2) | curses.A_BOLD,
                )
                self.stdscr.refresh()
                curses.napms(1500)
                return
            elif key == ord("n") or key == ord("N"):
                return

    def exercise_session(self):
        routine = LevelGenerator.generate_routine(
            self.user_state.current_level, self.user_state.current_day
        )
        self.stop_signal = False
        completed = True

        # Intro Screen
        self.stdscr.clear()
        self.center_text(
            f"LEVEL {routine.level} - DAY {routine.day}",
            y_offset=0,
            color_pair=curses.color_pair(3) | curses.A_BOLD,
        )
        self.center_text(
            f"Classic: {routine.classic_reps} | Pulse: {routine.pulse_reps}", y_offset=2
        )
        self.center_text("Press Any Key to Start...", y_offset=4)
        self.stdscr.getch()

        # CLASSIC LOOP
        for i in range(routine.classic_reps):
            if self.stop_signal:
                completed = False
                break

            # Pass current rep 'i' to display remaining count
            if not self.run_timer(routine.classic_hold_sec, "SQUEEZE", 1, routine, i):
                completed = False
                break

            if not self.run_timer(routine.classic_rest_sec, "REST", 2, routine, i):
                completed = False
                break

        # PULSE LOOP
        if completed:
            self.stdscr.clear()
            self.center_text("GET READY FOR PULSES!", y_offset=0)
            self.stdscr.refresh()
            curses.napms(2000)
            if not self.run_pulse(routine):
                completed = False

        # End Session
        self.stdscr.clear()
        if completed:
            self.user_state = self.state_manager.advance_progress(
                self.user_state, routine.total_days_in_level
            )
            self.center_text(
                "SESSION COMPLETE", color_pair=curses.color_pair(2) | curses.A_BOLD
            )
            self.center_text("Progress Saved.", y_offset=2)
        else:
            self.center_text(
                "SESSION STOPPED", color_pair=curses.color_pair(1) | curses.A_BOLD
            )

        self.stdscr.refresh()
        curses.napms(2000)

    def main_menu(self):
        while True:
            self.stdscr.clear()
            state = self.user_state

            self.draw_header()

            # Status Box (Simplified)
            self.center_text(
                f"Level: {state.current_level} | Day: {state.current_day}", y_offset=-2
            )
            last_date = state.last_performed[:10] if state.last_performed else "Never"
            self.center_text(f"Last Workout: {last_date}", y_offset=-1)

            # Menu
            self.center_text("[S]tart Workout", y_offset=2)
            self.center_text("[I]nfo [How-to]", y_offset=3)
            self.center_text("[P]rogress", y_offset=4)
            self.center_text("[Q]uit", y_offset=5)

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord("s") or key == ord("S"):
                self.exercise_session()
            elif key == ord("i") or key == ord("I"):
                self.info_screen()
            elif key == ord("p") or key == ord("P"):  # NEW
                self.progress_screen()
            elif key == ord("q") or key == ord("Q"):
                break

    def run(self, stdscr):
        self.stdscr = stdscr

        curses.curs_set(0)  # Hide cursor
        curses.start_color()
        curses.use_default_colors()

        # Define Colors: (ID, Foreground, Background)
        curses.init_pair(1, curses.COLOR_RED, -1)  # Squeeze
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # Rest
        curses.init_pair(3, curses.COLOR_WHITE, -1)  # Default
        curses.init_pair(4, curses.COLOR_CYAN, -1)  # Headers

        self.stdscr.timeout(100)

        self.main_menu()


def main():
    try:
        curses.wrapper(App().run)
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
