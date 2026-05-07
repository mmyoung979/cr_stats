from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_ids, count, players=None, evo_ids=None, hero_ids=None,
          card_names=None):
    n = len(card_ids)
    names = card_names or [chr(ord("A") + i) for i in range(n)]
    return {
        "id": hash(tuple(card_ids)),
        "hash": "h" + str(card_ids),
        "count": count,
        "card_ids": card_ids,
        "evo_card_ids": evo_ids or [],
        "hero_card_ids": hero_ids or [],
        "cards": [
            {"name": names[i], "id": card_ids[i]}
            for i in range(n)
        ],
        "players": players or [],
    }


def _no_variants(card_names):
    return {n: 0 for n in card_names}


class TestPickRecommendedDecks(TestCase):
    def test_full_ownership_ranked_by_count_descending(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        decks = [
            _deck(ids, 3, card_names=names),
            _deck(ids, 10, card_names=names),
            _deck(ids, 7, card_names=names),
        ]
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(decks, owned, levels, _no_variants(names), limit=3)
        self.assertEqual([d["count"] for d in result], [10, 7, 3])

    def test_excludes_decks_missing_any_card(self):
        ids = list(range(8))
        names_ok = [chr(ord("A") + i) for i in range(8)]
        deck_owned = _deck(ids, 5, card_names=names_ok)
        names_missing = names_ok[:7] + ["Z"]
        deck_missing = _deck(ids, 99, card_names=names_missing)
        owned = set(names_ok)
        levels = {n: 14 for n in names_ok}
        result = pick_recommended_decks(
            [deck_missing, deck_owned], owned, levels, _no_variants(names_ok), limit=3
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        decks = [_deck(ids, i, card_names=names) for i in range(1, 11)]
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(decks, owned, levels, _no_variants(names), limit=3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(pick_recommended_decks([], {"A"}, {"A": 14}, {"A": 0}), [])

    def test_no_owned_cards_returns_empty(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 5, card_names=names)
        self.assertEqual(pick_recommended_decks([deck], set(), {}, {}), [])

    def test_avg_level_computed_and_rounded(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 1, card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        levels[names[7]] = 1
        result = pick_recommended_decks([deck], owned, levels, _no_variants(names), limit=1)
        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        first = _deck(ids, 5, players=["#FIRST"], card_names=names)
        second = _deck(ids, 5, players=["#SECOND"], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        result = pick_recommended_decks(
            [first, second], owned, levels, _no_variants(names), limit=2
        )
        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])

    def test_deck_with_empty_cards_is_skipped(self):
        empty = {"id": 1, "hash": "h", "count": 99, "card_ids": [],
                 "evo_card_ids": [], "hero_card_ids": [], "cards": [],
                 "players": []}
        self.assertEqual(pick_recommended_decks([empty], {"A"}, {"A": 14}, {"A": 0}), [])

    def test_fully_playable_when_all_variants_unlocked(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], hero_ids=[ids[1]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        evos[names[0]] = 1  # evo bit
        evos[names[1]] = 2  # hero bit
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_missing_evo_variant_reported(self):
        ids = list(range(8))
        names = ["RG"] + [chr(ord("B") + i) for i in range(7)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "RG", "variant": "evolution"}],
        )

    def test_missing_hero_variant_reported(self):
        ids = list(range(8))
        names = ["A", "Bowler"] + [chr(ord("C") + i) for i in range(6)]
        deck = _deck(ids, 5, hero_ids=[ids[1]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "Bowler", "variant": "hero"}],
        )

    def test_partially_playable_demoted_below_fully_playable(self):
        ids = list(range(8))
        names = [chr(ord("A") + i) for i in range(8)]
        partial = _deck(ids, 99, evo_ids=[ids[0]], players=["#PARTIAL"], card_names=names)
        full = _deck(ids, 5, players=["#FULL"], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        result = pick_recommended_decks([partial, full], owned, levels, evos, limit=2)
        self.assertEqual(result[0]["players"], ["#FULL"])
        self.assertEqual(result[1]["players"], ["#PARTIAL"])

    def test_evolution_level_3_satisfies_both_slots(self):
        ids = list(range(8))
        names = ["Wizard"] + [chr(ord("B") + i) for i in range(7)]
        deck = _deck(ids, 5, evo_ids=[ids[0]], card_names=names)
        owned = set(names)
        levels = {n: 14 for n in names}
        evos = {n: 0 for n in names}
        evos["Wizard"] = 3
        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)
        self.assertTrue(result[0]["fully_playable"])
