from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.memory_manager import MemoryManager


def test_format_game_time_calendar():
    # Default is calendar
    # Base hour is 8
    res = MemoryManager.format_game_time(0)
    assert res == "Day 1, 08:00"
    
    res = MemoryManager.format_game_time(60)
    assert res == "Day 1, 09:00"
    
    res = MemoryManager.format_game_time(1440) # 24 hours
    assert res == "Day 2, 08:00"

def test_format_game_time_relative():
    config = {"day_label": "Sol"}
    res = MemoryManager.format_game_time(0, time_system="relative", time_config=config)
    assert res == "Sol 1, 08:00"
    
    res = MemoryManager.format_game_time(1440, time_system="relative", time_config=config)
    assert res == "Sol 2, 08:00"

def test_format_game_time_custom_start():
    config = {"start_time": "10:00", "day_label": "Cycle"}
    res = MemoryManager.format_game_time(0, time_system="relative", time_config=config)
    assert res == "Cycle 1, 10:00"
    
    res = MemoryManager.format_game_time(120, time_system="relative", time_config=config)
    assert res == "Cycle 1, 12:00"

def test_format_game_time_overflow():
    config = {"start_time": "23:00"}
    res = MemoryManager.format_game_time(120, time_system="relative", time_config=config)
    # 23:00 + 2h = 01:00 next day
    assert res == "Day 2, 01:00"

def test_format_game_time_start_with_minutes():
    config = {"start_time": "08:30"}
    res = MemoryManager.format_game_time(0, time_system="relative", time_config=config)
    assert res == "Day 1, 08:30"

    res = MemoryManager.format_game_time(30, time_system="relative", time_config=config)
    assert res == "Day 1, 09:00"

    res = MemoryManager.format_game_time(90, time_system="relative", time_config=config)
    assert res == "Day 1, 10:00"

def test_resolve_start_datetime_uses_configured_start_time():
    # Without any manifest date, the start_time from time_config must be honored.
    manifest = {"time_config": {}}
    res = AdventureLogic.resolve_start_datetime(manifest, time_config={"start_time": "14:30"})
    assert res == "2026-01-01T14:30:00"

    # start_time should be preferred over the 08:00 default even with a year override.
    manifest = {"time_config": {"start_year_override": 2133}}
    res = AdventureLogic.resolve_start_datetime(manifest, time_config={"start_time": "09:15"})
    assert res == "2133-01-01T09:15:00"

def test_resolve_start_datetime_defaults_to_eight():
    # Without any time_config, no explicit start datetime can be resolved.
    assert AdventureLogic.resolve_start_datetime({}) is None
    assert AdventureLogic.resolve_start_datetime({"time_config": {}}, time_config={}) is None

def test_resolve_start_datetime_prefers_explicit_start_datetime():
    manifest = {"start_datetime": "2026-04-17T10:00:00"}
    res = AdventureLogic.resolve_start_datetime(manifest, time_config={"start_time": "14:30"})
    assert res == "2026-04-17T10:00:00"
