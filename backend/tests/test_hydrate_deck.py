from unittest import TestCase

from apis.utils.decks import hydrate_deck


def _card_row(card_id, name, elixir_cost=3, has_evolution=False, has_hero=False):
    return {
        "id": card_id,
        "name": name,
        "rarity": "common",
        "elixir_cost": elixir_cost,
        "max_level": 16,
        "has_evolution": has_evolution,
        "has_hero": has_hero,
        "icon_url": f"{name}.png",
        "evolution_icon_url": f"{name}-evo.png" if has_evolution else None,
        "hero_icon_url": f"{name}-hero.png" if has_hero else None,
    }


class TestHydrateDeck(TestCase):
    def test_orders_evos_first_then_heroes_then_regulars_by_elixir(self):
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
        # Remaining 6 are sorted by elixir cost ascending
        remaining = [c["elixir_cost"] for c in result[2:]]
        self.assertEqual(remaining, sorted(remaining))

    def test_active_form_set_per_card(self):
        cards_by_id = {
            1: _card_row(1, "EvoCard", has_evolution=True),
            2: _card_row(2, "HeroCard", has_hero=True),
            3: _card_row(3, "Plain"),
            4: _card_row(4, "Plain2"),
            5: _card_row(5, "Plain3"),
            6: _card_row(6, "Plain4"),
            7: _card_row(7, "Plain5"),
            8: _card_row(8, "Plain6"),
        }
        deck_row = {
            "card_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "evo_card_ids": [1],
            "hero_card_ids": [2],
        }
        result = hydrate_deck(deck_row, cards_by_id)
        forms = {c["name"]: c["activeForm"] for c in result}
        self.assertEqual(forms["EvoCard"], "evolution")
        self.assertEqual(forms["HeroCard"], "hero")
        self.assertIsNone(forms["Plain"])

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
            "hasEvolution", "hasHero", "elixir_cost", "activeForm",
        })
        self.assertEqual(first["icon"], "Furnace.png")
        self.assertEqual(first["evolvedIcon"], "Furnace-evo.png")
        self.assertEqual(first["activeForm"], "evolution")

    def test_skips_unknown_card_ids(self):
        # If a card_id is missing from cards_by_id, skip it (defensive).
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
