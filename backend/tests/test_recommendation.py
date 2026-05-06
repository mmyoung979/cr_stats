from unittest import TestCase

from apis.utils.recommendation import pick_recommended_decks


def _deck(card_names, count, players=None, variants=None):
    """Build a deck dict like the snapshot stored in common_decks.

    `variants` is an optional list of (has_evolution, has_hero) tuples per slot.
    Defaults to (False, False) for every slot, i.e. no variants required.
    """
    if variants is None:
        variants = [(False, False)] * len(card_names)
    return {
        "count": count,
        "cards": [
            {
                "name": n,
                "icon": f"{n}.png",
                "hasEvolution": ev,
                "hasHero": hero,
            }
            for n, (ev, hero) in zip(card_names, variants)
        ],
        "players": players or [],
    }


def _no_variants(card_names):
    return {n: 0 for n in card_names}


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

        result = pick_recommended_decks(decks, owned, levels, _no_variants(cards), limit=3)

        self.assertEqual([d["count"] for d in result], [10, 7, 3])

    def test_excludes_decks_missing_any_card(self):
        deck_owned = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        deck_missing = _deck(["A", "B", "C", "D", "E", "F", "G", "Z"], count=99)
        owned = {"A", "B", "C", "D", "E", "F", "G", "H"}
        levels = {n: 14 for n in owned}

        result = pick_recommended_decks(
            [deck_missing, deck_owned], owned, levels, _no_variants(owned), limit=3
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 5)

    def test_respects_limit(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        decks = [_deck(cards, count=i) for i in range(1, 11)]
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(decks, owned, levels, _no_variants(cards), limit=3)

        self.assertEqual(len(result), 3)
        self.assertEqual([d["count"] for d in result], [10, 9, 8])

    def test_empty_deck_list_returns_empty(self):
        self.assertEqual(
            pick_recommended_decks([], {"A"}, {"A": 14}, {"A": 0}), []
        )

    def test_no_owned_cards_returns_empty(self):
        deck = _deck(["A", "B", "C", "D", "E", "F", "G", "H"], count=5)
        self.assertEqual(pick_recommended_decks([deck], set(), {}, {}), [])

    def test_avg_level_computed_and_rounded(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(cards, count=1)
        owned = set(cards)
        # Levels: 14,14,14,14,14,14,14,1 -> mean 12.375 -> rounds to 12.4
        levels = {n: 14 for n in cards}
        levels["H"] = 1

        result = pick_recommended_decks([deck], owned, levels, _no_variants(cards), limit=1)

        self.assertEqual(result[0]["avg_level"], 12.4)

    def test_tie_on_count_preserves_input_order(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        first = _deck(cards, count=5, players=["#FIRST"])
        second = _deck(cards, count=5, players=["#SECOND"])
        owned = set(cards)
        levels = {n: 14 for n in cards}

        result = pick_recommended_decks(
            [first, second], owned, levels, _no_variants(cards), limit=2
        )

        self.assertEqual(result[0]["players"], ["#FIRST"])
        self.assertEqual(result[1]["players"], ["#SECOND"])

    def test_deck_with_empty_cards_is_skipped(self):
        empty = {"count": 99, "cards": [], "players": []}
        self.assertEqual(
            pick_recommended_decks([empty], {"A"}, {"A": 14}, {"A": 0}), []
        )

    def test_fully_playable_when_all_variants_unlocked(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Slot 0 needs evo, slot 1 needs hero.
        deck = _deck(
            cards,
            count=5,
            variants=[(True, False), (False, True), (False, False), (False, False),
                      (False, False), (False, False), (False, False), (False, False)],
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}
        evos["A"] = 1  # evo bit
        evos["B"] = 2  # hero bit

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_missing_evo_variant_reported(self):
        cards = ["RG", "B", "C", "D", "E", "F", "G", "H"]
        deck = _deck(
            cards,
            count=5,
            variants=[(True, False)] + [(False, False)] * 7,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # RG evo NOT unlocked

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "RG", "slot": 0, "variant": "evolution"}],
        )

    def test_missing_hero_variant_reported(self):
        cards = ["A", "Bowler", "C", "D", "E", "F", "G", "H"]
        deck = _deck(
            cards,
            count=5,
            variants=[(False, False), (False, True)] + [(False, False)] * 6,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # Bowler hero NOT unlocked

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertFalse(result[0]["fully_playable"])
        self.assertEqual(
            result[0]["missing_variants"],
            [{"name": "Bowler", "slot": 1, "variant": "hero"}],
        )

    def test_partially_playable_demoted_below_fully_playable(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Partial deck: count=99 but slot 0 needs evo we lack.
        partial = _deck(
            cards,
            count=99,
            variants=[(True, False)] + [(False, False)] * 7,
            players=["#PARTIAL"],
        )
        # Full deck: count=5, no variants required.
        full = _deck(cards, count=5, players=["#FULL"])
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # No variants unlocked

        result = pick_recommended_decks([partial, full], owned, levels, evos, limit=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["players"], ["#FULL"])
        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[1]["players"], ["#PARTIAL"])
        self.assertFalse(result[1]["fully_playable"])

    def test_slots_3_through_7_dont_trigger_variant_check(self):
        cards = ["A", "B", "C", "D", "E", "F", "G", "H"]
        # Slots 0-2 have no variants; slots 3-7 have hasEvolution=True but
        # should NOT trigger an unlock check because variant slots are 0-2 only.
        deck = _deck(
            cards,
            count=5,
            variants=[(False, False)] * 3 + [(True, False)] * 5,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}  # Nothing unlocked anywhere

        result = pick_recommended_decks([deck], owned, levels, evos, limit=1)

        self.assertTrue(result[0]["fully_playable"])
        self.assertEqual(result[0]["missing_variants"], [])

    def test_evolution_level_3_satisfies_both_slots(self):
        cards = ["Wizard", "B", "C", "D", "E", "F", "G", "H"]
        # Same card in slot 0 (needs evo) and (hypothetically) implied hero
        # via a second deck — verify the bitmask check.
        evo_deck = _deck(
            cards, count=5, variants=[(True, True)] + [(False, False)] * 7
        )
        hero_deck = _deck(
            ["B", "Wizard", "C", "D", "E", "F", "G", "H"],
            count=4,
            variants=[(False, False), (True, True)] + [(False, False)] * 6,
        )
        owned = set(cards)
        levels = {n: 14 for n in cards}
        evos = {n: 0 for n in cards}
        evos["Wizard"] = 3  # Both variants unlocked

        result = pick_recommended_decks(
            [evo_deck, hero_deck], owned, levels, evos, limit=2
        )

        self.assertTrue(result[0]["fully_playable"])
        self.assertTrue(result[1]["fully_playable"])
