﻿from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RightsStates(StatesGroup):
    waiting_confirmation = State()

