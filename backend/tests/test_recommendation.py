from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_names, count, players=None):
    return {
        "count": count,
        "cards": [{"name": n, "icon": f"{n}.png"} for n in card_names],
        "players": players or [],
    }


class TestPickRecommendedDecks(TestCase):
    def test_full_ownership_ranked_by_count_descending(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [
            _deck(cards, count=3),
            _deck(cards, count=10),
            _deck(cards, count=7),
        ]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, limit=3)

        self.assertEqual([d["count"] for d in result], [10, 7, 3])

    def test_excludes_decks_missing_any_card(self):
        deck_owned = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        deck_missing = _deck(["A", "B", "C", "D", "E", "F", "G", "Z"], count=99)
        owned = {"A", "B", "C", "D", "E", "F", "G", "H"}
        levels = {n: 14 for n in owned}

        result = pick_recommended_decks([deck_missing, deck_owned], owned, levels, limit=3)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [_deck(cards, count=i) for i in range(1, 11)]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(pick_recommended_decks([], {"A"}, {"A": 14}), [])

    def test_no_owned_cards_returns_empty(self):
        deck = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        self.assertEqual(pick_recommended_decks([deck], set(), {}), [])

    def test_avg_level_computed_and_rounded(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(cards, count=1)
        owned = set(cards)
        # Levels: 14,14,14,14,14,14,14,1 -> mean 12.375 -> rounds to 12.4
        levels = {n: 14 for n in cards}
        levels["H"] = 1

        result = pick_recommended_decks([deck], owned, levels, limit=1)

        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        first = _deck(cards, count=5, players=["#FIRST"])
        second = _deck(cards, count=5, players=["#SECOND"])
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks([first, second], owned, levels, limit=2)

        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])
