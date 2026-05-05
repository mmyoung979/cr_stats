#!/usr/bin/env python3

# Python imports
import json
from datetime import datetime

# Local imports
from scripts.utils.data_utils import (
    get_battlelog_data,
    get_battle_rows,
    get_card_data,
    get_deck_data,
)

if __name__ == "__main__":
    player_count: int = 50
    battlelog_data, rank_by_tag = get_battlelog_data(player_count)

    # card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    # print(card_data)

    # deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)
    # print(deck_data)

    rows = get_battle_rows(battlelog_data, rank_by_tag)
    print(f"battle_rows count: {len(rows)}")
    print("--- first 2 rows ---")

    def encode(obj):
        return obj.isoformat() if isinstance(obj, datetime) else str(obj)

    print(json.dumps(rows[:2], indent=2, default=encode))
