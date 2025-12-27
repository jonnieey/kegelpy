#!/usr/bin/env python3
import os
import curses
import time
import math

# Try to import plotext, fall back gracefully
try:
    import plotext as plt

    HAVE_PLOTEXT = True
except ImportError:
    HAVE_PLOTEXT = False
    plt = None

from .core import (
    get_app_data_file,
    LevelGenerator,
    StateManager,
    StatisticsCalculator,
)

DATA_FILE = get_app_data_file()


class App:
    def __init__(self):
        self.state_manager = StateManager(DATA_FILE)
        self.user_state = self.state_manager.load()
        self.stdscr = None
        self.paused = False
        self.stop_signal = False
        self.session_start_time = None
        self.stats_calculator = StatisticsCalculator()

        # Colors
        self.COLOR_SQUEEZE = 1
        self.COLOR_REST = 2
        self.COLOR_DEFAULT = 3
        self.COLOR_HEADER = 4
        self.COLOR_STATS = 5

    def center_text(self, text, y_offset=0, color_pair=0, attr=0):
        """Helper to center text on screen."""
        height, width = self.stdscr.getmaxyx()
        x = max(0, int((width // 2) - (len(text) // 2)))
        y = max(0, int((height // 2) + y_offset))

        # Safety check to prevent crashing if terminal is too small
        if y < height and x + len(text) < width:
            if attr:
                self.stdscr.addstr(y, x, text, color_pair | attr)
            else:
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
            # For pulse phase, we need to know which set and which rep in that set
            # This is handled in run_pulse itself, so we'll just show generic info
            # total_pulse_reps = sum(routine.pulse_reps)
            pulse_str = f"Pulse Sets: {len(routine.pulse_reps)}"
            self.center_text(pulse_str, y_offset=-4)
            reps_str = f"Reps per set: {routine.pulse_reps}"
            self.center_text(reps_str, y_offset=-3)

        # --- CLASSIC PHASE (Active) ---
        elif current_classic_rep is not None:
            remaining = routine.classic_reps - current_classic_rep
            classic_str = f"Classic Reps: {remaining}/{routine.classic_reps}"
            self.center_text(classic_str, y_offset=-4)

        # --- PRE-START (Show both totals) ---
        else:
            # When exercise hasn't started yet
            classic_str = f"Classic Reps: {routine.classic_reps}"
            pulse_sets_str = f"Pulse Sets: {len(routine.pulse_reps)}"
            pulse_reps_str = f"Reps per set: {routine.pulse_reps}"
            self.center_text(classic_str, y_offset=-4)
            self.center_text(pulse_sets_str, y_offset=-3)
            self.center_text(pulse_reps_str, y_offset=-2)

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
                y_offset=-10,
                color_pair=curses.color_pair(3) | curses.A_BOLD | curses.A_UNDERLINE,
            )

            # Classic Instructions
            self.center_text(
                "1. CLASSIC KEGELS",
                y_offset=-8,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(
                "Identify your pelvic floor muscles (used to stop urine).", y_offset=-7
            )
            self.center_text("SQUEEZE: Tighten these muscles and hold.", y_offset=-6)
            self.center_text("REST: Completely relax the muscles.", y_offset=-5)

            # Pulse Instructions
            self.center_text(
                "2. PULSE KEGELS",
                y_offset=-3,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(
                "Rapidly tighten and relax the pelvic floor muscles.", y_offset=-2
            )
            self.center_text(
                "Do not hold. Squeeze then immediately release.", y_offset=-1
            )

            # General Tips
            self.center_text(
                "3. GENERAL TIPS",
                y_offset=1,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text("• Breathe normally throughout the exercises.", y_offset=2)
            self.center_text(
                "• Avoid tensing your abdomen, buttocks, or thighs.", y_offset=3
            )
            self.center_text("• Focus only on your pelvic floor muscles.", y_offset=4)
            self.center_text(
                "• Start slowly and gradually increase intensity.", y_offset=5
            )
            self.center_text(
                "• Consistency is more important than intensity.", y_offset=6
            )

            # Important Notes
            self.center_text(
                "4. IMPORTANT NOTES",
                y_offset=8,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text("• Stop if you feel pain or discomfort.", y_offset=9)
            self.center_text(
                "• Consult a healthcare professional if you have concerns.", y_offset=10
            )
            self.center_text(
                "• Perfect your technique before increasing difficulty.", y_offset=11
            )

            # Footer
            self.center_text(
                "Press [q] to Return to Menu",
                y_offset=13,
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

    def statistics_screen(self):
        """Displays exercise statistics with visualizations."""
        while True:
            self.stdscr.clear()
            self.draw_header()

            # Calculate statistics
            stats = self.stats_calculator.calculate_stats(
                self.user_state.exercise_history
            )
            #
            height, width = self.stdscr.getmaxyx()

            # Convert total duration to hours and minutes
            total_hours = int(stats["total_duration_minutes"] // 60)
            total_minutes = int(stats["total_duration_minutes"] % 60)

            if total_hours > 0:
                duration_str = f"{total_hours}h {total_minutes}m"
            else:
                duration_str = f"{total_minutes}m"

            self.center_text(f"Total Duration: {duration_str}", y_offset=-3)
            self.center_text(f"Workout Days: {stats['workout_days']}", y_offset=-2)
            self.center_text(f"Total Workouts: {stats['total_workouts']}", y_offset=-1)

            footer_y = height - 3
            if footer_y < height:
                text = (
                    "[V]isualize  [Q]uit to Menu" if HAVE_PLOTEXT else "[Q]uit to Menu"
                )

                if HAVE_PLOTEXT:
                    self.stdscr.addstr(
                        footer_y,
                        width // 2 - 15,
                        text,
                        curses.color_pair(3),
                    )

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord("q") or key == ord("Q"):
                break
            elif key == ord("v") or key == ord("V"):
                if HAVE_PLOTEXT:
                    # Ask user which visualization style they want
                    self.stdscr.clear()
                    self.center_text(
                        "VISUALIZATION STYLE",
                        y_offset=-5,
                        color_pair=curses.color_pair(4) | curses.A_BOLD,
                    )
                    self.center_text("[S]tandard Graphs", y_offset=-2)
                    self.center_text("[C]ompact View", y_offset=-1)
                    self.center_text("[B]ack to Stats", y_offset=0)
                    self.stdscr.refresh()

                    self.stdscr.timeout(-1)
                    key = self.stdscr.getch()
                    if key == ord("s") or key == ord("S"):
                        self.show_visualizations(stats)
                    elif key == ord("c") or key == ord("C"):
                        self.show_compact_visualizations(stats)
                # if HAVE_PLOTEXT:
                #     self.show_visualizations(stats)
                else:
                    # Show message that plotext is not available
                    self.stdscr.clear()
                    self.center_text(
                        "Plotext not installed for visualizations.", y_offset=0
                    )
                    self.center_text("Install with: pip install plotext", y_offset=1)
                    self.center_text("Press any key to continue...", y_offset=3)
                    self.stdscr.refresh()
                    self.stdscr.getch()

    def show_visualizations(self, stats):
        """Show visualizations using plotext."""
        curses.endwin()

        try:
            print("\n" + "=" * 60)
            print("KEGELPY STATISTICS VISUALIZATION")
            print("=" * 60)

            # Visualization 1: Last 14 Days
            if any(day["duration_minutes"] > 0 for day in stats["last_14_days"]):
                print("\n📊 LAST 14 DAYS WORKOUT DURATION\n")

                dates = [day["date"][5:] for day in stats["last_14_days"]]  # MM-DD
                durations = [day["duration_minutes"] for day in stats["last_14_days"]]

                plt.clear_figure()
                plt.bar(dates, durations, color="green")
                plt.title("Workout Duration by Day (Last 14 Days)")
                plt.xlabel("Date")
                plt.ylabel("Minutes")

                # *** PLOTEXT COLOR FIX ***
                plt.clear_color()  # Forces the plot to render without ANSI color codes

                plt.show()

            # Visualization 2: Level Statistics
            if stats["level_stats"]:
                print("\n📈 LEVEL STATISTICS\n")

                levels = list(stats["level_stats"].keys())
                level_durations = list(stats["level_stats"].values())

                # Sort by level
                sorted_pairs = sorted(zip(levels, level_durations))
                levels = [str(pair[0]) for pair in sorted_pairs]
                level_durations = [pair[1] for pair in sorted_pairs]

                plt.clear_figure()
                plt.bar(levels, level_durations, color="blue")
                plt.title("Average Duration by Level")
                plt.xlabel("Level")
                plt.ylabel("Average Minutes per Session")

                # *** PLOTEXT COLOR FIX ***
                plt.clear_color()  # Forces the plot to render without ANSI color codes

                plt.show()

            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            # ... (rest of summary code) ...

            print("\n" + "=" * 60)
            print("Press Enter to return to the statistics screen...")
            input()

        except Exception as e:
            print(f"\nError showing visualizations: {e}")
            print("Press Enter to continue...")
            input()

        # Reinitialize curses
        self.stdscr.clear()
        self.stdscr.refresh()

    def show_compact_visualizations(self, stats):
        """Show visualizations using plotext in a compact format."""
        # We'll temporarily exit curses mode to use plotext
        curses.endwin()

        try:
            # Get terminal size
            import shutil

            term_size = shutil.get_terminal_size()
            term_width = term_size.columns
            # term_height = term_size.lines

            # Calculate compact plot dimensions
            plot_width = min(70, term_width - 10)  # Leave margins
            plot_height = 8  # Fixed height for compactness

            # Visualization 1: Last 14 Days
            if any(day["duration_minutes"] > 0 for day in stats["last_14_days"]):
                print("\n📊 LAST 14 DAYS WORKOUT DURATION\n")

                dates = [day["date"][5:] for day in stats["last_14_days"]]  # MM-DD
                durations = [day["duration_minutes"] for day in stats["last_14_days"]]

                plt.clear_figure()
                plt.plot_size(plot_width, plot_height)

                # Use simple bar for compactness
                plt.simple_bar(dates, durations, color="green")
                plt.title("Last 14 Days")
                plt.xlabel("Date")
                plt.ylabel("Minutes")
                plt.grid(False)  # No grid for cleaner look
                plt.show()

            # Visualization 2: Level Statistics
            if stats["level_stats"]:
                print("\n📈 LEVEL STATISTICS\n")

                levels = list(stats["level_stats"].keys())
                level_durations = list(stats["level_stats"].values())

                # Sort by level
                sorted_pairs = sorted(zip(levels, level_durations))
                levels = [str(pair[0]) for pair in sorted_pairs]
                level_durations = [pair[1] for pair in sorted_pairs]

                plt.clear_figure()
                plt.plot_size(plot_width, plot_height)

                plt.simple_bar(levels, level_durations, color="blue")
                plt.title("Average Duration by Level")
                plt.xlabel("Level")
                plt.ylabel("Avg Minutes")
                plt.grid(False)
                plt.show()

            # Compact summary

            print("=" * min(60, term_width - 10))
            print("\nPress Enter to return...")

            # Wait for Enter key
            import sys

            while True:
                try:
                    ch = sys.stdin.read(1)
                    if ch == "\n":
                        break
                except Exception:
                    break

        except Exception as e:
            print(f"\nError showing visualizations: {e}")
            print("Press Enter to continue...")
            try:
                input()
            except Exception:
                pass

        # Reinitialize curses
        self.stdscr.clear()
        self.stdscr.refresh()

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

            # Calculate display seconds - show ceil of remaining, but never show 0
            display_seconds = math.ceil(remaining)

            # Skip if we've reached 0 seconds (time to exit)
            if display_seconds <= 0:
                break

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

            # Timer Number - only show positive seconds
            self.center_text(f"{display_seconds}s", y_offset=2)

            self.center_text(
                "[p]ause  [s]top", y_offset=8, color_pair=curses.color_pair(3)
            )

            self.stdscr.refresh()
            curses.napms(100)  # Sleep 100ms to reduce CPU usage

        return True

    def run_pulse(self, routine):
        """Runs the rapid pulse phase with three separate sets."""
        total_sets = len(routine.pulse_reps)  # Should be 3

        for set_idx, reps_in_set in enumerate(routine.pulse_reps):
            if self.stop_signal:
                return False

            # Show set information
            self.stdscr.clear()
            self.draw_header()
            self.draw_status(routine)
            self.center_text(
                f"Pulse Set {set_idx + 1}/{total_sets}",
                y_offset=-4,
                color_pair=curses.color_pair(4) | curses.A_BOLD,
            )
            self.center_text(f"Reps in this set: {reps_in_set}", y_offset=-3)
            self.stdscr.refresh()
            curses.napms(1000)  # Brief pause before starting set

            # Run the reps in this set
            for rep_in_set in range(reps_in_set):
                if self.stop_signal:
                    return False

                # Calculate remaining reps in this set
                remaining_in_set = reps_in_set - rep_in_set

                # Squeeze Phase (0.6 seconds)
                start_sq = time.time()
                while time.time() - start_sq < 0.6:
                    if self.handle_input():
                        return False
                    self.stdscr.clear()
                    self.draw_header()
                    self.draw_status(routine)

                    # Show pulse progress with decreasing countdown
                    pulse_str = f"Set {set_idx + 1}/{total_sets}: Rep {remaining_in_set}/{reps_in_set}"
                    self.center_text(pulse_str, y_offset=-4)

                    self.center_text(
                        "SQUEEZE",
                        y_offset=0,
                        color_pair=curses.color_pair(1) | curses.A_BOLD,
                    )
                    self.stdscr.refresh()
                    curses.napms(50)

                # Release Phase (0.6 seconds)
                start_rel = time.time()
                while time.time() - start_rel < 0.6:
                    if self.handle_input():
                        return False
                    self.stdscr.clear()
                    self.draw_header()
                    self.draw_status(routine)

                    # Show pulse progress with decreasing countdown
                    pulse_str = f"Set {set_idx + 1}/{total_sets}: Rep {remaining_in_set}/{reps_in_set}"
                    self.center_text(pulse_str, y_offset=-4)

                    self.center_text(
                        "RELEASE",
                        y_offset=0,
                        color_pair=curses.color_pair(2) | curses.A_BOLD,
                    )
                    self.stdscr.refresh()
                    curses.napms(50)

            # Rest between sets (except after last set)
            if set_idx < total_sets - 1:
                if self.stop_signal:
                    return False

                # Show rest countdown
                self.stdscr.clear()
                self.draw_header()
                self.draw_status(routine)
                # self.center_text(
                #     f"Set {set_idx + 1} Complete!",
                #     y_offset=-2,
                #     color_pair=curses.color_pair(2) | curses.A_BOLD,
                # )
                # self.center_text("10-second rest between sets...", y_offset=0)
                self.stdscr.refresh()

                # Countdown rest period
                rest_start = time.time()
                rest_duration = 10.0
                while time.time() - rest_start < rest_duration:
                    if self.stop_signal:
                        return False
                    if self.handle_input():
                        # If pause triggered, break and handle it
                        if self.paused:
                            self.pause_screen()

                    # Calculate remaining rest time
                    remaining_rest = max(
                        0.0, rest_duration - (time.time() - rest_start)
                    )

                    # Update display
                    self.stdscr.clear()
                    self.draw_header()
                    self.draw_status(routine)
                    self.center_text(
                        f"Set {set_idx + 1} Complete!",
                        y_offset=-2,
                        color_pair=curses.color_pair(2) | curses.A_BOLD,
                    )
                    self.center_text(
                        f"Rest: {math.ceil(remaining_rest)}s",
                        y_offset=0,
                        color_pair=curses.color_pair(3) | curses.A_BOLD,
                    )
                    self.stdscr.refresh()
                    curses.napms(100)

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
                # Create a fresh UserState but preserve app settings if any
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

        # Record start time
        session_start_time = time.time()

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

        # Calculate session duration
        session_duration = time.time() - session_start_time

        # End Session
        self.stdscr.clear()
        if completed:
            # Add exercise record to history
            self.user_state = self.state_manager.add_exercise_record(
                self.user_state, routine, session_duration
            )
            # Advance progress
            self.user_state = self.state_manager.advance_progress(
                self.user_state, routine.total_days_in_level
            )

            # Show completion with duration
            minutes = int(session_duration // 60)
            seconds = int(session_duration % 60)

            self.center_text(
                "SESSION COMPLETE",
                y_offset=-2,
                color_pair=curses.color_pair(2) | curses.A_BOLD,
            )
            self.center_text(f"Duration: {minutes}m {seconds}s", y_offset=-1)
            self.center_text("Progress Saved.", y_offset=1)
        else:
            self.center_text(
                "SESSION STOPPED",
                y_offset=0,
                color_pair=curses.color_pair(1) | curses.A_BOLD,
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

            # Show quick stats if available
            if state.exercise_history:
                stats = self.stats_calculator.calculate_stats(state.exercise_history)
                total_min = int(stats["total_duration_minutes"])
                if total_min > 60:
                    hours = total_min // 60
                    mins = total_min % 60
                    stats_str = (
                        f"Total: {hours}h {mins}m | Days: {stats['workout_days']}"
                    )
                else:
                    stats_str = f"Total: {total_min}m | Days: {stats['workout_days']}"

                self.center_text(stats_str, y_offset=0, color_pair=curses.color_pair(5))

            # Menu
            self.center_text("[S]tart Workout", y_offset=2)
            self.center_text("[I]nfo [How-to]", y_offset=3)
            self.center_text("[P]rogress", y_offset=4)
            self.center_text("[T]rack Stats", y_offset=5)  # NEW: Statistics option
            self.center_text("[Q]uit", y_offset=6)

            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord("s") or key == ord("S"):
                self.exercise_session()
            elif key == ord("i") or key == ord("I"):
                self.info_screen()
            elif key == ord("p") or key == ord("P"):
                self.progress_screen()
            elif key == ord("t") or key == ord("T"):  # NEW: Statistics
                self.statistics_screen()
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
        curses.init_pair(5, curses.COLOR_YELLOW, -1)  # Stats

        self.stdscr.timeout(100)

        self.main_menu()


def main():
    try:
        curses.wrapper(App().run)
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
