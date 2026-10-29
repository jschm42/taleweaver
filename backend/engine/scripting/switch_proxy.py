"""
Switch proxy models for TaleWeaver scripting engine.

Provides read and write access to switch states, state inspection,
and state mutations with optional outcome triggering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.engine.scripting.context import GameContext, ScriptChangeset


class SwitchProxy:
    """Safe proxy for inspecting and mutating an individual switch entity."""

    def __init__(
        self,
        entity_id: str,
        entity_data: dict[str, Any],
        changeset: ScriptChangeset,
        context: Optional[GameContext] = None,
    ):
        self._id = entity_id
        self._data = entity_data
        self._changeset = changeset
        self._context = context

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return str(self._data.get("name", self._id))

    @property
    def states(self) -> list[str]:
        """Returns the list of valid states configured for this switch."""
        from backend.engine.interaction.switch_service import SwitchService

        cfg = SwitchService.resolve_switch_config(self._data)
        states = cfg.get("states")
        if isinstance(states, list) and states:
            return [str(s).strip().upper() for s in states if str(s).strip()]
        return ["OFF", "ON"]

    @property
    def initial_state(self) -> str:
        """Returns the initial state configured for this switch."""
        from backend.engine.interaction.switch_service import SwitchService

        cfg = SwitchService.resolve_switch_config(self._data)
        init = cfg.get("initial_state")
        if init and str(init).strip():
            return str(init).strip().upper()
        return self.states[0] if self.states else "OFF"

    @property
    def state(self) -> str:
        """Returns the current state of the switch (reflecting script updates first)."""
        # 1. Check pending mutations in the current changeset
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and "switch_state" in upd:
                return str(upd["switch_state"]).strip().upper()

        # 2. Check session entity state
        session_st = self._data.get("switch_state")
        if session_st is not None and str(session_st).strip():
            return str(session_st).strip().upper()

        # 3. Fallback to configured initial_state
        return self.initial_state

    @state.setter
    def state(self, val: str) -> None:
        self.set_state(val)

    @property
    def switch_state(self) -> str:
        """Alias for state."""
        return self.state

    @property
    def label(self) -> str:
        """In-game text of the current state: its label, or the state ID."""
        from backend.engine.interaction.switch_service import SwitchService
        from backend.engine.interaction.switch_states import state_label

        return state_label(SwitchService.resolve_switch_config(self._data), self.state)

    @switch_state.setter
    def switch_state(self, val: str) -> None:
        self.set_state(val)

    def get_state(self) -> str:
        """Reads and returns the current state of the switch."""
        return self.state

    def is_state(self, target_state: str) -> bool:
        """Checks if the switch is in target_state (case-insensitive)."""
        return self.state == str(target_state).strip().upper()

    def set_state(self, target_state: str, apply_outcomes: bool = True) -> None:
        """
        Sets the switch directly to target_state.
        If apply_outcomes is True, applies configured outcomes for this state.
        """
        clean_target = str(target_state).strip().upper()
        self._changeset.entity_updates.append({"entity_id": self._id, "switch_state": clean_target})
        if apply_outcomes:
            self._apply_configured_outcomes(clean_target)

    def flip(self, target_state: Optional[str] = None, apply_outcomes: bool = True) -> str:
        """
        Flips the switch to target_state, or toggles to the alternate state if omitted.
        Returns the resulting state.
        """
        if target_state is not None and str(target_state).strip():
            new_target = str(target_state).strip().upper()
        else:
            available = self.states
            current = self.state
            if len(available) >= 2:
                try:
                    idx = available.index(current)
                    new_target = available[(idx + 1) % len(available)]
                except ValueError:
                    new_target = available[1] if available[0] == current else available[0]
            else:
                new_target = "ON" if current == "OFF" else "OFF"

        self.set_state(new_target, apply_outcomes=apply_outcomes)
        return new_target

    def toggle(self, apply_outcomes: bool = True) -> str:
        """Toggles the switch between its states. Returns the new state."""
        return self.flip(apply_outcomes=apply_outcomes)

    def _apply_outcome_effect(self, eff: dict[str, Any]) -> None:
        eff_type = str(eff.get("type") or "").strip().lower()
        if eff_type == "story_flag":
            key = str(eff.get("key") or "").strip()
            if key:
                self._changeset.var_updates[f"__flag_{key}"] = True
                self._changeset.var_updates[key] = True
                self._changeset.story_flag_updates[key] = True
            return

        if eff_type == "unlock_exit" and self._context:
            target_id = str(eff.get("target_id") or "").strip()
            if target_id:
                self._context.exits.unlock(target_id)
            return

        if eff_type == "unlock_container" and self._context:
            target_id = str(eff.get("target_id") or "").strip()
            if target_id:
                self._context.objects.get(target_id).unlock()

    def _apply_configured_outcomes(self, on_state: str) -> None:
        """Applies configured outcomes for on_state directly to the ScriptChangeset."""
        from backend.engine.interaction.switch_service import SwitchService

        cfg = SwitchService.resolve_switch_config(self._data)
        outcomes = cfg.get("outcomes")
        if not isinstance(outcomes, list):
            return

        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            if str(outcome.get("on_state") or "").strip().upper() != on_state:
                continue
            effects = outcome.get("effects")
            if not isinstance(effects, list):
                continue
            for eff in effects:
                if isinstance(eff, dict):
                    self._apply_outcome_effect(eff)


class SwitchesProxy:
    """Safe proxy for querying and operating all switch entities in the adventure."""

    def __init__(
        self,
        entities: dict[str, dict[str, Any]],
        changeset: ScriptChangeset,
        context: Optional[GameContext] = None,
    ):
        self._entities = entities
        self._changeset = changeset
        self._context = context

    def _find_entity_data(self, switch_id_or_name: str) -> tuple[str, dict[str, Any]]:
        target_raw = str(switch_id_or_name).strip()
        target_upper = target_raw.upper()
        if target_raw in self._entities:
            return target_raw, self._entities[target_raw]

        for eid, data in self._entities.items():
            if str(eid).strip().upper() == target_upper:
                return eid, data

        target_lower = target_raw.lower()
        for eid, data in self._entities.items():
            if str(data.get("name", "")).strip().lower() == target_lower:
                return eid, data

        return target_raw, {"id": target_raw, "name": target_raw}

    def get(self, switch_id_or_name: str) -> SwitchProxy:
        """Returns a SwitchProxy for the specified switch ID or name."""
        eid, data = self._find_entity_data(switch_id_or_name)
        return SwitchProxy(eid, data, self._changeset, self._context)

    def get_state(self, switch_id_or_name: str, default: str = "") -> str:
        """Reads the current state of the switch; returns default if no such switch exists."""
        eid, _data = self._find_entity_data(switch_id_or_name)
        if default and eid not in self._entities:
            return str(default).strip().upper()
        return self.get(switch_id_or_name).get_state()

    def set_state(self, switch_id_or_name: str, state: str, apply_outcomes: bool = True) -> None:
        """Sets the state of the switch."""
        self.get(switch_id_or_name).set_state(state, apply_outcomes=apply_outcomes)

    def set(self, switch_id_or_name: str, state: str, apply_outcomes: bool = True) -> None:
        """Alias for set_state()."""
        self.set_state(switch_id_or_name, state, apply_outcomes=apply_outcomes)

    def is_state(self, switch_id_or_name: str, state: str) -> bool:
        """Returns True if the switch is currently in the specified state."""
        return self.get(switch_id_or_name).is_state(state)

    def flip(
        self,
        switch_id_or_name: str,
        target_state: Optional[str] = None,
        apply_outcomes: bool = True,
    ) -> str:
        """Flips/toggles the switch. Returns the new state."""
        return self.get(switch_id_or_name).flip(
            target_state=target_state, apply_outcomes=apply_outcomes
        )

    def toggle(self, switch_id_or_name: str, apply_outcomes: bool = True) -> str:
        """Toggles the switch. Returns the new state."""
        return self.get(switch_id_or_name).toggle(apply_outcomes=apply_outcomes)

    def all(self) -> list[SwitchProxy]:
        """Returns proxies for all configured switches."""
        from backend.engine.interaction.switch_service import SwitchService

        result = []
        for eid, data in self._entities.items():
            item_type = str(data.get("item_type") or "").strip().upper()
            if item_type == "SWITCH" or bool(SwitchService.resolve_switch_config(data)):
                result.append(self.get(eid))
        return result

    def exists(self, switch_id_or_name: str) -> bool:
        """Checks if an entity with this ID or name exists."""
        target_upper = str(switch_id_or_name).strip().upper()
        if target_upper in {str(e).upper() for e in self._entities}:
            return True
        target_lower = str(switch_id_or_name).strip().lower()
        return any(
            str(data.get("name", "")).strip().lower() == target_lower
            for data in self._entities.values()
        )

    def __getitem__(self, switch_id_or_name: str) -> str:
        return self.get_state(switch_id_or_name)

    def __setitem__(self, switch_id_or_name: str, state: str) -> None:
        self.set_state(switch_id_or_name, state)
