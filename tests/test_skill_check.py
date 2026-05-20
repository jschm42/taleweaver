import pytest
from unittest.mock import patch
from backend.models.avatar import Avatar
from backend.engine.skill_check import roll_attack

def test_roll_attack_standard_hit():
    # Arrange
    avatar = Avatar(
        name="Test Hero",
        dexterity=10,
        hp=100,
        max_hp=100,
        stamina=100,
        max_stamina=100,
        strength=10,
        stats={"dexterity": 10}
    )
    
    # Mock random.randint to roll a 15 (not critical for DEX 10, threshold is 20)
    # And mock damage rolls to roll 5 for 1d8
    with patch("random.randint") as mock_rand:
        mock_rand.side_effect = [15, 5]  # d20 roll, then 1d8 roll
        
        # Act
        res = roll_attack(avatar, "dexterity", 16, "1d8+2")
        
        # Assert
        assert res["hit_roll"] == 15
        assert res["is_hit"] is True
        assert res["is_crit"] is False
        assert res["damage_total"] == 7  # 5 + 2

def test_roll_attack_critical_hit():
    # Arrange
    # Dexterity 18: crit threshold is 20 - (18-10)//4 = 20 - 2 = 18
    avatar = Avatar(
        name="Dexterous Hero",
        dexterity=18,
        hp=100,
        max_hp=100,
        stamina=100,
        max_stamina=100,
        strength=10,
        stats={"dexterity": 18}
    )
    
    # Mock random.randint to roll a 18 (critical)
    # And mock damage rolls to roll 6 for 1d8
    with patch("random.randint") as mock_rand:
        mock_rand.side_effect = [18, 6]  # d20 roll, then 1d8 roll
        
        # Act
        res = roll_attack(avatar, "dexterity", 25, "1d8+2")  # target AC 25 (standard roll would miss, but crit hits)
        
        # Assert
        assert res["hit_roll"] == 18
        assert res["is_crit"] is True
        assert res["is_hit"] is True
        assert res["damage_total"] == 16  # (6 + 2) * 2 = 16

def test_roll_attack_clamped_crit_threshold():
    # Arrange
    # Dexterity 38: threshold calculation: 20 - (38-10)//4 = 20 - 7 = 13.
    # Clamped to minimum threshold of 15.
    avatar = Avatar(
        name="Godlike Dex Hero",
        dexterity=38,
        hp=100,
        max_hp=100,
        stamina=100,
        max_stamina=100,
        strength=10,
        stats={"dexterity": 38}
    )
    
    # Mock random.randint to roll 14 (not crit, threshold is clamped to 15) and 15 (crit)
    with patch("random.randint") as mock_rand:
        mock_rand.side_effect = [14, 5, 15, 5]
        
        res1 = roll_attack(avatar, "dexterity", 30, "1d8")
        assert res1["is_crit"] is False
        
        res2 = roll_attack(avatar, "dexterity", 30, "1d8")
        assert res2["is_crit"] is True
