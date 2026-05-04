#!/usr/bin/env python3

# Python imports
import json

# Local imports
from scripts.utils.data_utils import get_battlelog_data, get_card_data, get_deck_data

if __name__ == "__main__":
    player_count: int = 50
    battlelog_data = get_battlelog_data(player_count)

    # card_data = json.dumps(get_card_data(battlelog_data), indent=2)
    # print(card_data)

    deck_data = json.dumps(get_deck_data(battlelog_data), indent=2)
    print(deck_data)
