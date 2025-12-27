import sys
import os
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from collections import defaultdict


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


@dataclass
class ExerciseRecord:
    date: str  # ISO format date
    level: int
    day: int
    duration_seconds: float
    classic_reps: int
    pulse_reps: List[int]


@dataclass
class Routine:
    level: int
    day: int
    classic_hold_sec: int
    classic_rest_sec: int
    classic_reps: int
    pulse_reps: List[int]
    total_days_in_level: int


@dataclass
class UserState:
    current_level: int = 1
    current_day: int = 1
    last_performed: str = ""
    exercise_history: List[ExerciseRecord] = field(default_factory=list)


class LevelGenerator:
    PULSE_SETS = 3
    REST_BETWEEN_PULSE_SETS = 10

    @staticmethod
    def get_days_for_level(level: int) -> int:
        """Calculate number of days in a level based on progression patterns."""
        if level <= 3:
            return 5
        elif level <= 6:
            return 6
        elif level <= 10:
            # Levels 7-10: 6 days + increasing gradually
            return 6 + min(2, (level - 6) // 2)
        elif level <= 15:
            # Levels 11-15: 7-8 days range
            return 7 + min(1, (level - 11) // 4)
        else:
            # Levels 16+: Cap at 12 days, increase slowly
            return min(12, 8 + (level - 15) // 3)

    @staticmethod
    def classic_hold(level: int, day: int) -> int:
        """Calculate classic hold time based on level and day."""
        base = 4  # Starting base

        if level <= 10:
            # Levels 1-10: Gradual increase
            base = 3 + level
            # Apply day adjustments for higher levels
            if level >= 7 and day >= 4:
                base += 1
        else:
            # Levels 11+: More sophisticated progression
            if level <= 14:
                base = 11 + (level - 10)
                # Level 12 has mid-level increase
                if level == 12 and day >= 4:
                    base += 2
            else:
                # Levels 15+: Progressive increase
                base = 14 + (level - 14) // 2
                # Every few days within level, hold time might increase
                if day >= (LevelGenerator.get_days_for_level(level) // 2):
                    base += 1

        # Ensure minimum and maximum bounds
        return min(30, max(4, base))

    @staticmethod
    def classic_rest(level: int) -> int:
        """Calculate classic rest time based on level."""
        if level < 11:
            return 4
        else:
            return 5

    @staticmethod
    def classic_reps(level: int, day: int) -> int:
        """Calculate number of classic reps based on level and day."""
        # Base formula
        if level <= 10:
            base = 10 + level
            # Day-based progression
            day_adjustment = (day - 1) // 3  # Increase every 3 days
            return base + day_adjustment
        else:
            # Levels 11+: Different progression pattern
            base = 15
            # Level-specific adjustments
            if level == 11:
                if day >= 6:
                    return 16
            elif level == 12:
                if day <= 3:
                    return 16
                else:
                    return 15
            elif level == 13:
                if day == 1:
                    return 15
                else:
                    return 16
            elif level >= 14:
                return 16

            return base

    @staticmethod
    def pulse_reps(level: int, day: int) -> List[int]:
        """
        Calculate pulse reps for each of the three sets.
        Returns list of 3 integers representing reps for each set.
        """
        # Base pulse reps calculation
        if level <= 10:
            base_reps = 10 + (level * 2)
        else:
            # Levels 11+: Different base calculation
            base_reps = 25 + (level - 10) * 2

        # Day adjustments - pulse reps increase every few days
        day_adjustment = (day - 1) // 2

        # Generate three sets with staggered progression
        # Pattern from YAML: first set advances first, then second, then third
        sets = []

        for set_num in range(3):
            # Each set starts at different points
            set_adjustment = day_adjustment

            # First set advances immediately
            # Second set advances after first set has established
            if set_num == 1:
                set_adjustment = max(0, day_adjustment - 1)
            # Third set advances last
            elif set_num == 2:
                set_adjustment = max(0, day_adjustment - 2)

            set_reps = base_reps + set_adjustment

            # Ensure minimum reps
            sets.append(max(5, set_reps))

        return sets

    @staticmethod
    def generate_routine(level: int, day: int) -> Routine:
        """Generate a complete routine for the given level and day."""
        pulse_reps_list = LevelGenerator.pulse_reps(level, day)

        return Routine(
            level=level,
            day=day,
            classic_hold_sec=LevelGenerator.classic_hold(level, day),
            classic_rest_sec=LevelGenerator.classic_rest(level),
            classic_reps=LevelGenerator.classic_reps(level, day),
            pulse_reps=pulse_reps_list,
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
                # Handle migration from old format
                if "exercise_history" not in data:
                    data["exercise_history"] = []
                else:
                    # Convert history dicts to ExerciseRecord objects
                    history_data = data.get("exercise_history", [])
                    exercise_history = []
                    for record in history_data:
                        # Ensure all required fields exist
                        if isinstance(record, dict):
                            exercise_history.append(ExerciseRecord(**record))
                    data["exercise_history"] = exercise_history

                return UserState(**data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Error loading state: {e}")
            return UserState()

    def save(self, state: UserState):
        # Convert ExerciseRecord objects to dicts for JSON serialization
        state_dict = asdict(state)
        with open(self.filepath, "w") as f:
            json.dump(state_dict, f, indent=4)

    def add_exercise_record(
        self, state: UserState, routine: Routine, duration_seconds: float
    ) -> UserState:
        """Add a new exercise record to history."""
        record = ExerciseRecord(
            date=datetime.now().isoformat(),
            level=routine.level,
            day=routine.day,
            duration_seconds=duration_seconds,
            classic_reps=routine.classic_reps,
            pulse_reps=routine.pulse_reps,  # This is now a list
        )
        state.exercise_history.append(record)
        state.last_performed = record.date
        self.save(state)
        return state

    def advance_progress(
        self, state: UserState, days_in_current_level: int
    ) -> UserState:
        if state.current_day >= days_in_current_level:
            state.current_level += 1
            state.current_day = 1
        else:
            state.current_day += 1
        self.save(state)
        return state


class StatisticsCalculator:
    @staticmethod
    def calculate_stats(exercise_history: List[ExerciseRecord]) -> Dict:
        """Calculate various statistics from exercise history."""
        if not exercise_history:
            return {
                "total_duration_minutes": 0,
                "workout_days": 0,
                "last_14_days": [],
                "level_stats": {},
                "total_workouts": 0,
                "avg_duration_minutes": 0,
            }

        # Total duration in minutes
        total_duration_seconds = sum(
            record.duration_seconds for record in exercise_history
        )
        total_duration_minutes = total_duration_seconds / 60

        # Unique workout days
        workout_dates = set()
        for record in exercise_history:
            date_only = record.date.split("T")[0]  # Extract YYYY-MM-DD
            workout_dates.add(date_only)

        # Last 14 days data
        last_14_days = []
        today = datetime.now().date()
        for i in range(14):
            current_date = today - timedelta(days=13 - i)  # Start from 14 days ago
            date_str = current_date.isoformat()

            # Calculate total duration for this day
            day_duration = 0
            for record in exercise_history:
                record_date = record.date.split("T")[0]
                if record_date == date_str:
                    day_duration += record.duration_seconds

            last_14_days.append(
                {"date": date_str, "duration_minutes": day_duration / 60}
            )

        # Level statistics
        level_stats = defaultdict(float)
        level_counts = defaultdict(int)
        for record in exercise_history:
            level_stats[record.level] += (
                record.duration_seconds / 60
            )  # Convert to minutes
            level_counts[record.level] += 1

        # Calculate average duration per level
        avg_level_stats = {}
        for level in level_stats:
            if level_counts[level] > 0:
                avg_level_stats[level] = level_stats[level] / level_counts[level]

        return {
            "total_duration_minutes": total_duration_minutes,
            "workout_days": len(workout_dates),
            "total_workouts": len(exercise_history),
            "avg_duration_minutes": total_duration_minutes / len(exercise_history)
            if exercise_history
            else 0,
            "last_14_days": last_14_days,
            "level_stats": dict(avg_level_stats),
        }
