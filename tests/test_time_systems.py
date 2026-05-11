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
