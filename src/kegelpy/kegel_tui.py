#!/usr/bin/env python3
import os
import asyncio
import math
from datetime import datetime

# Textual Imports
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, Label, ProgressBar, Digits
from textual.reactive import reactive
from textual.binding import Binding

# Statistics Visualization
from textual_plotext import PlotextPlot

from .core import (
    ExerciseRecord,
    UserState,
    LevelGenerator,
    StateManager,
    get_app_data_file,
)


# --- SCREENS ---


class MainMenu(Screen):
    """Vim-like navigation for the main menu."""

    BINDINGS = [
        Binding("j", "focus_next", "Down", show=False),
        Binding("k", "focus_previous", "Up", show=False),
        Binding("s", "start", "Start"),
        Binding("i", "info", "Info"),
        Binding("p", "progress", "Progress"),
        Binding("t", "stats", "Stats"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("=== KEGELPY ===", id="title"),
            Static(id="status_box"),
            Vertical(
                Button("Start Workout (s)", variant="success", id="start"),
                Button("How-to Info (i)", variant="primary", id="info"),
                Button("Progress & Reset (p)", variant="default", id="progress"),
                Button("Statistics (t)", variant="default", id="stats"),
                Button("Quit (q)", variant="error", id="quit"),
                classes="menu_buttons",
            ),
            id="main_container",
        )
        yield Footer()

    def on_mount(self):
        self.update_status()
        self.query_one("#start").focus()

    def update_status(self):
        state = self.app.user_state
        last = state.last_performed[:10] if state.last_performed else "Never"

        # Generate current routine to show pulse set info
        routine = LevelGenerator.generate_routine(
            state.current_level, state.current_day
        )

        # Format pulse reps as a string
        pulse_info = f"Pulse sets: {routine.pulse_reps}"

        status = (
            f"Level: {state.current_level} | Day: {state.current_day}\n"
            f"Last: {last}\n"
            f"Classic: {routine.classic_reps} reps\n"
            f"{pulse_info}"
        )
        self.query_one("#status_box").update(status)

    def action_start(self):
        self.app.push_screen(WorkoutScreen())

    def action_info(self):
        self.app.push_screen(InfoScreen())

    def action_progress(self):
        self.app.push_screen(ProgressScreen())

    def action_stats(self):
        self.app.push_screen(StatisticsScreen())

    def action_quit(self):
        self.app.exit()


class WorkoutScreen(Screen):
    """Timer screen with integer countdowns and centered progress."""

    BINDINGS = [
        Binding("p", "pause_resume", "Pause/Resume"),
        Binding("q", "stop", "Stop/Quit"),
        Binding("s", "stop", "Stop/Quit", show=False),
    ]

    phase = reactive("GET READY")
    timer_text = reactive("0")
    rep_text = reactive("")
    progress = reactive(0.0)
    is_paused = False
    current_phase_label = "GET READY"
    current_pulse_set = 0
    total_pulse_sets = 3

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(id="phase_display"),
            Digits(id="timer_display"),
            Static(id="rep_display"),
            Static(id="set_display"),
            Vertical(
                ProgressBar(
                    total=100, show_eta=False, show_percentage=False, id="pbar"
                ),
                id="pbar_container",
            ),
            classes="timer_container",
        )
        yield Footer()

    def on_mount(self):
        self.workout_worker = self.run_workout()

    def watch_phase(self, value):
        self.query_one("#phase_display").update(value)

    def watch_timer_text(self, value):
        self.query_one("#timer_display").update(value)

    def watch_rep_text(self, value):
        self.query_one("#rep_display").update(value)

    def watch_progress(self, value):
        self.query_one("#pbar").progress = value

    def action_pause_resume(self):
        self.is_paused = not self.is_paused
        self.phase = "PAUSED" if self.is_paused else self.current_phase_label

    def action_stop(self):
        if hasattr(self, "workout_worker"):
            self.workout_worker.cancel()
        self.app.pop_screen()

    @work(exclusive=True)
    async def run_workout(self):
        routine = LevelGenerator.generate_routine(
            self.app.user_state.current_level, self.app.user_state.current_day
        )
        start_time = datetime.now()

        # 1. Classic Reps
        for i in range(routine.classic_reps):
            # Calculate remaining classic reps (decreasing countdown)
            remaining_classic = routine.classic_reps - i
            self.rep_text = f"Classic Reps Remaining: {remaining_classic}"
            await self.countdown(routine.classic_hold_sec, "SQUEEZE", "classic-active")
            await self.countdown(routine.classic_rest_sec, "REST", "classic-rest")

        # 2. Pulse Sets - Now multiple sets with different rep counts
        self.phase = "GET READY FOR PULSES!"
        self.query_one("#set_display").update("")
        await asyncio.sleep(1.5)

        # Loop through each pulse set (should be 3 sets)
        for set_num, reps_in_set in enumerate(routine.pulse_reps):
            self.current_pulse_set = set_num + 1
            self.total_pulse_sets = len(routine.pulse_reps)

            # Show set information
            self.phase = f"PULSE SET {self.current_pulse_set}/{self.total_pulse_sets}"
            set_display = self.query_one("#set_display")
            set_display.update(f"Reps in this set: {reps_in_set}")
            await asyncio.sleep(1.0)

            # Run reps in this set
            for rep_num in range(reps_in_set):
                # Calculate remaining reps in this set
                remaining_in_set = reps_in_set - rep_num
                self.rep_text = f"Pulse Reps Remaining: {remaining_in_set}"

                await self.countdown(0.6, "PULSE SQUEEZE", "pulse-active")
                await self.countdown(0.6, "RELEASE", "pulse-rest")

            # Rest between sets (except after last set)
            if set_num < len(routine.pulse_reps) - 1:
                self.phase = f"SET {self.current_pulse_set} COMPLETE"
                self.rep_text = "10-second rest between sets..."
                set_display.update("")
                await self.countdown(10, "REST BETWEEN SETS", "classic-rest")

        # Save and Finish
        duration = (datetime.now() - start_time).total_seconds()
        self.app.save_workout(routine, duration)
        self.phase = "COMPLETE!"
        self.rep_text = "Great job!"
        await asyncio.sleep(2)
        self.app.pop_screen()

    async def countdown(self, seconds, label, css_class):
        self.current_phase_label = label
        self.phase = label
        container = self.query_one(".timer_container")
        container.set_class(True, css_class)

        remaining = float(seconds)
        while remaining > 0:
            if not self.is_paused:
                # Calculate display seconds - ceil of remaining, but never show 0
                display_seconds = math.ceil(remaining)

                # Only update if we have positive seconds to display
                if display_seconds > 0:
                    self.timer_text = str(display_seconds)

                    # CHANGED: Math inverted so bar moves Left -> Right
                    # (Elapsed time / Total time) * 100
                    elapsed = seconds - remaining
                    self.progress = (elapsed / seconds) * 100

                await asyncio.sleep(0.1)
                remaining -= 0.1
            else:
                await asyncio.sleep(0.1)

        # Ensure bar hits 100% at the very end
        self.progress = 100.0
        container.set_class(False, css_class)


class InfoScreen(Screen):
    BINDINGS = [
        Binding("q", "app.pop_screen", "Back (q)"),
        Binding("j", "scroll_down", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("HOW TO KEGEL", classes="header"),
            Static("\n1. CLASSIC KEGELS", classes="sub-header"),
            Static(
                "SQUEEZE: Tighten pelvic floor muscles and hold.\nREST: Completely relax."
            ),
            Static("\n2. PULSE KEGELS", classes="sub-header"),
            Static("Rapidly tighten and relax. Squeeze then immediately release."),
            Static("\n3. GENERAL TIPS", classes="sub-header"),
            Static(
                "• Breathe normally throughout the exercises.\n"
                "• Avoid tensing your abdomen, buttocks, or thighs.\n"
                "• Focus only on your pelvic floor muscles.\n"
                "• Start slowly and gradually increase intensity.\n"
                "• Consistency is more important than intensity."
            ),
            Static("\n4. IMPORTANT NOTES", classes="sub-header"),
            Static(
                "• Stop if you feel pain or discomfort.\n"
                "• Consult a healthcare professional if you have concerns.\n"
                "• Perfect your technique before increasing difficulty."
            ),
            id="info_text",
        )
        yield Footer()


class ProgressScreen(Screen):
    BINDINGS = [
        Binding("q", "app.pop_screen", "Back (q)"),
        Binding("j", "focus_next", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("CURRENT PROGRESS", classes="header"),
            Label(id="prog_details"),
            Button("Reset All Progress", variant="error", id="reset_btn"),
            classes="centered_content",
        )
        yield Footer()

    def on_mount(self):
        u = self.app.user_state
        # Generate current routine to show details
        routine = LevelGenerator.generate_routine(u.current_level, u.current_day)

        details = (
            f"Level: {u.current_level}\n"
            f"Day: {u.current_day}\n"
            f"Classic Reps: {routine.classic_reps}\n"
            f"Pulse Sets: {routine.pulse_reps}\n"
            f"Total Days in Level: {routine.total_days_in_level}"
        )
        self.query_one("#prog_details").update(details)
        self.query_one("#reset_btn").focus


class StatisticsScreen(Screen):
    BINDINGS = [Binding("q", "app.pop_screen", "Back (q)")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield PlotextPlot(id="duration_plot")
            yield PlotextPlot(id="level_plot")
        yield Footer()

    def on_mount(self):
        history = self.app.user_state.exercise_history
        if not history:
            return

        # Duration Plot
        dp = self.query_one("#duration_plot")
        dp.plt.clear_figure()
        dates = [r.date[5:10] for r in history[-7:]]
        durs = [r.duration_seconds / 60 for r in history[-7:]]
        dp.plt.bar(dates, durs, color="green")
        dp.plt.title("Minutes (Last 7 Sessions)")
        dp.refresh()

        # Level Plot
        lp = self.query_one("#level_plot")
        lp.plt.clear_figure()
        lvls = {}
        for r in history:
            lvls[r.level] = lvls.get(r.level, 0) + (r.duration_seconds / 60)
        lp.plt.bar([str(k) for k in lvls.keys()], list(lvls.values()), color="blue")
        lp.plt.title("Total Time per Level")
        lp.refresh()


# --- MAIN APP ---


class KegelApp(App):
    CSS = """
    #main_container { align: center middle; }
    #title { text-align: center; color: $accent; text-style: bold; margin-bottom: 1; }
    #status_box { text-align: center; border: double $primary; padding: 1; margin: 1; height: 5; }
    
    .menu_buttons { width: 40; align: center middle; }
    .menu_buttons Button { width: 100%; margin: 0; align: center middle; }
    
    .centered_content { align: center middle; text-align: center; }
    .header { text-align: center; color: $accent; text-style: bold underline; margin: 1; }
    .sub-header { color: $secondary; text-style: bold; }
    
    .timer_container { align: center middle; }
    #phase_display { text-style: bold; text-align: center; height: 3; content-align: center middle; }
    #timer_display { text-align: center; margin: 1; }
    #rep_display { text-align: center; color: $text-muted; margin-bottom: 1; }
    #set_display { text-align: center; color: $secondary; text-style: italic; margin-bottom: 1; }
    
    /* Phase Background Colors */
    .classic-active { background: maroon; color: white; }
    .classic-rest { background: darkgreen; color: white; }
    .pulse-active { background: red; color: white; }
    .pulse-rest { background: green; color: white; }
    """

    def on_mount(self):
        self.data_path = get_app_data_file()
        self.state_manager = StateManager(self.data_path)
        self.user_state = self.state_manager.load()
        self.push_screen(MainMenu())

    @on(Button.Pressed, "#start")
    def start_workout(self):
        self.push_screen(WorkoutScreen())

    @on(Button.Pressed, "#info")
    def show_info(self):
        self.push_screen(InfoScreen())

    @on(Button.Pressed, "#progress")
    def show_progress(self):
        self.push_screen(ProgressScreen())

    @on(Button.Pressed, "#stats")
    def show_stats(self):
        self.push_screen(StatisticsScreen())

    @on(Button.Pressed, "#quit")
    def quit_app(self):
        self.exit()

    def save_workout(self, routine, duration):
        record = ExerciseRecord(
            date=datetime.now().isoformat(),
            level=routine.level,
            day=routine.day,
            duration_seconds=duration,
            classic_reps=routine.classic_reps,
            pulse_reps=routine.pulse_reps,  # This is now a list
        )
        self.user_state.exercise_history.append(record)
        self.user_state.last_performed = record.date

        if self.user_state.current_day >= routine.total_days_in_level:
            self.user_state.current_level += 1
            self.user_state.current_day = 1
        else:
            self.user_state.current_day += 1

        self.state_manager.save(self.user_state)
        for screen in self.screen_stack:
            if isinstance(screen, MainMenu):
                screen.update_status()

    def reset_data(self):
        if os.path.exists(self.data_path):
            os.remove(self.data_path)
        self.user_state = UserState()
        self.state_manager.save(self.user_state)


def main():
    app = KegelApp()
    app.run()


if __name__ == "__main__":
    main()
