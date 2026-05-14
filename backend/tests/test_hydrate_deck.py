from unittest import TestCase

from apis.utils.decks import hydrate_deck


def _card_row(card_id, name, elixir_cost=3, has_evolution=False, has_hero=False,
              rarity="common"):
    return {
        "id": card_id,
        "name": name,
        "rarity": rarity,
        "elixir_cost": elixir_cost,
        "max_level": 16,
        "has_evolution": has_evolution,
        "has_hero": has_hero,
        "icon_url": f"{name}.png",
        "evolution_icon_url": f"{name}-evo.png" if has_evolution else None,
        "hero_icon_url": f"{name}-hero.png" if has_hero else None,
    }


class TestHydrateDeck(TestCase):
    def test_one_evo_one_hero_renders_evo_hero_then_regulars(self):
        cards_by_id = {
            1: _card_row(1, "EvoCard", elixir_cost=4, has_evolution=True),
            2: _card_row(2, "HeroCard", elixir_cost=5, has_hero=True),
            3: _card_row(3, "Cheap", elixir_cost=1),
            4: _card_row(4, "Mid", elixir_cost=3),
            5: _card_row(5, "Big", elixir_cost=7),
            6: _card_row(6, "Small", elixir_cost=2),
            7: _card_row(7, "Med2", elixir_cost=4),
            8: _card_row(8, "Filler", elixir_cost=3),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        names = [c["name"] for c in result]
        self.assertEqual(names[0], "EvoCard")
        self.assertEqual(names[1], "HeroCard")
        # Slots 2-7 (indices 2-7) are regulars sorted by elixir
        remaining = [c["elixirCost"] for c in result[2:]]
        self.assertEqual(remaining, sorted(remaining))

    def test_two_evos_one_hero_renders_evo_hero_evo(self):
        # User-stated rule: "If a deck has 2 evos and a hero, the order
        # must be evo, hero, evo." Slot 0 takes evo, slot 1 takes hero,
        # slot 2 takes the remaining evo.
        cards_by_id = {
            1: _card_row(1, "FirstEvo", has_evolution=True),
            2: _card_row(2, "Hero", has_hero=True),
            3: _card_row(3, "SecondEvo", has_evolution=True),
            4: _card_row(4, "Reg1"),
            5: _card_row(5, "Reg2"),
            6: _card_row(6, "Reg3"),
            7: _card_row(7, "Reg4"),
            8: _card_row(8, "Reg5"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1, 3],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = [(c["name"], c["activeForm"]) for c in result]
        self.assertEqual(forms[0][1], "evolution")
        self.assertEqual(forms[1][1], "hero")
        self.assertEqual(forms[2][1], "evolution")
        # Slots 3-7 are regulars
        for name, form in forms[3:]:
            self.assertIsNone(form)

    def test_one_evo_two_heroes_renders_evo_hero_hero(self):
        cards_by_id = {
            1: _card_row(1, "Evo", has_evolution=True),
            2: _card_row(2, "Hero1", has_hero=True),
            3: _card_row(3, "Hero2", has_hero=True),
            4: _card_row(4, "Reg1"),
            5: _card_row(5, "Reg2"),
            6: _card_row(6, "Reg3"),
            7: _card_row(7, "Reg4"),
            8: _card_row(8, "Reg5"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [2, 3],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = [c["activeForm"] for c in result]
        self.assertEqual(forms[:3], ["evolution", "hero", "hero"])

    def test_two_evos_zero_heroes_renders_evo_regular_evo(self):
        # Slot 1 is hero/champion only — without a hero or champion, slot 1
        # is a regular card. The second evo falls back to slot 2.
        cards_by_id = {
            1: _card_row(1, "Evo1", has_evolution=True),
            2: _card_row(2, "Evo2", has_evolution=True),
            3: _card_row(3, "Reg1"),
            4: _card_row(4, "Reg2"),
            5: _card_row(5, "Reg3"),
            6: _card_row(6, "Reg4"),
            7: _card_row(7, "Reg5"),
            8: _card_row(8, "Reg6"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1, 2],
            "hero_card_ids": [],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = [c["activeForm"] for c in result]
        self.assertEqual(forms[:3], ["evolution", None, "evolution"])

    def test_champion_placed_in_slot_1(self):
        # Champion goes in slot 1 (preferred), evos in slot 0 and slot 2.
        cards_by_id = {
            1: _card_row(1, "Tesla", has_evolution=True),
            2: _card_row(2, "MightyMiner", rarity="champion"),
            3: _card_row(3, "Firecracker", has_evolution=True),
            4: _card_row(4, "Reg1"),
            5: _card_row(5, "Reg2"),
            6: _card_row(6, "Reg3"),
            7: _card_row(7, "Reg4"),
            8: _card_row(8, "Reg5"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1, 3],
            "hero_card_ids": [],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = [(c["name"], c["activeForm"]) for c in result]
        self.assertEqual(forms[1], ("MightyMiner", "champion"))
        self.assertEqual(forms[0][1], "evolution")
        self.assertEqual(forms[2][1], "evolution")
        # Slots 3-7 are regulars
        for name, form in forms[3:]:
            self.assertIsNone(form)

    def test_champion_takes_precedence_over_hero_in_slot_1(self):
        # Champion gets slot 1, hero falls to slot 2.
        cards_by_id = {
            1: _card_row(1, "Champ", rarity="champion"),
            2: _card_row(2, "Hero", has_hero=True),
            3: _card_row(3, "Reg1"),
            4: _card_row(4, "Reg2"),
            5: _card_row(5, "Reg3"),
            6: _card_row(6, "Reg4"),
            7: _card_row(7, "Reg5"),
            8: _card_row(8, "Reg6"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = [(c["name"], c["activeForm"]) for c in result]
        self.assertEqual(forms[0][1], None)  # slot 0 has no evo, fills with regular
        self.assertEqual(forms[1], ("Champ", "champion"))
        self.assertEqual(forms[2], ("Hero", "hero"))

    def test_no_variants_renders_all_regulars_by_elixir(self):
        cards_by_id = {
            i: _card_row(i, f"C{i}", elixir_cost=10 - i)
            for i in range(1, 9)
        }
        deck_row = {
            "card_ids": list(range(1, 9)),
            "evo_card_ids": [],
            "hero_card_ids": [],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        elixirs = [c["elixirCost"] for c in result]
        self.assertEqual(elixirs, sorted(elixirs))

    def test_emits_expected_card_shape(self):
        cards_by_id = {
            1: _card_row(1, "Furnace", has_evolution=True),
            2: _card_row(2, "B"),
            3: _card_row(3, "C"),
            4: _card_row(4, "D"),
            5: _card_row(5, "E"),
            6: _card_row(6, "F"),
            7: _card_row(7, "G"),
            8: _card_row(8, "H"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        first = result[0]
        self.assertEqual(set(first.keys()), {
            "name", "icon", "evolvedIcon", "heroIcon",
            "hasEvolution", "hasHero", "elixirCost", "activeForm",
        })
        self.assertEqual(first["icon"], "Furnace.png")
        self.assertEqual(first["evolvedIcon"], "Furnace-evo.png")
        self.assertEqual(first["activeForm"], "evolution")

    def test_skips_unknown_card_ids(self):
        cards_by_id = {
            1: _card_row(1, "A"),
            2: _card_row(2, "B"),
        }
        deck_row = {"card_ids": [1, 2, 999], "evo_card_ids": [], "hero_card_ids": []}
        result = hydrate_deck(deck_row, cards_by_id)
        self.assertEqual(len(result), 2)
        self.assertEqual({c["name"] for c in result}, {"A", "B"})

    def test_empty_deck_returns_empty(self):
        self.assertEqual(
            hydrate_deck({"card_ids": [], "evo_card_ids": [], "hero_card_ids": []}, {}),
            [],
        )
