import hashlib
from unittest import TestCase

from scripts.utils.data_utils import infer_deck


def _card(card_id, name, has_evo=False, has_hero=False):
    icons = {"medium": f"{name}.png"}
    if has_evo:
        icons["evolutionMedium"] = f"{name}-evo.png"
    if has_hero:
        icons["heroMedium"] = f"{name}-hero.png"
    return {"id": card_id, "name": name, "iconUrls": icons}


def _expected_hash(card_ids, evo_ids, hero_ids):
    payload = (
        "|".join(str(i) for i in sorted(card_ids))
        + "::"
        + "|".join(str(i) for i in sorted(evo_ids))
        + "::"
        + "|".join(str(i) for i in sorted(hero_ids))
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class TestInferDeck(TestCase):
    def test_no_variants_when_no_variant_cards_in_first_three_slots(self):
        cards = [_card(i, chr(ord("A") + i)) for i in range(8)]
        result = infer_deck(cards)
        self.assertEqual(result["card_ids"], sorted(c["id"] for c in cards))
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [])
        self.assertEqual(
            result["hash"], _expected_hash(result["card_ids"], [], [])
        )

    def test_evo_only_in_slot_0(self):
        cards = [_card(0, "Furnace", has_evo=True)] + [
            _card(i, chr(ord("A") + i)) for i in range(1, 8)
        ]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [0])
        self.assertEqual(result["hero_card_ids"], [])

    def test_hero_only_in_slot_1(self):
        cards = [
            _card(0, "Furnace"),
            _card(1, "Bowler", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [1])

    def test_evo_fallback_in_slot_1(self):
        # slot 1 has hasEvolution but NOT hasHero -> falls back to evo
        cards = [
            _card(0, "Furnace"),
            _card(1, "Tesla", has_evo=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [1])
        self.assertEqual(result["hero_card_ids"], [])

    def test_three_form_slots_filled(self):
        cards = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
            _card(2, "Balloon", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(3, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [0])
        self.assertEqual(result["hero_card_ids"], [1, 2])

    def test_dual_variant_in_hero_slot_picks_hero(self):
        # Wizard has both evo and hero; in slot 1 it's hero
        cards = [
            _card(0, "Furnace"),
            _card(1, "Wizard", has_evo=True, has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        result = infer_deck(cards)
        self.assertEqual(result["evo_card_ids"], [])
        self.assertEqual(result["hero_card_ids"], [1])

    def test_hash_is_order_insensitive_for_regular_slots(self):
        # Same 8 cards, same form choices, different slot 3-7 order -> same hash
        cards_a = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(2, 8)]
        cards_b = [
            _card(0, "Furnace", has_evo=True),
            _card(1, "Bowler", has_hero=True),
        ] + list(reversed([_card(i, chr(ord("A") + i)) for i in range(2, 8)]))
        self.assertEqual(infer_deck(cards_a)["hash"], infer_deck(cards_b)["hash"])

    def test_hash_changes_when_evo_choice_changes(self):
        cards_a = [
            _card(0, "Furnace", has_evo=True),
        ] + [_card(i, chr(ord("A") + i)) for i in range(1, 8)]
        # Same 8 cards but Furnace is now in slot 3 (regular form, not evo)
        cards_b = [
            _card(1, "B"), _card(2, "C"), _card(3, "D"),
            _card(0, "Furnace", has_evo=True),  # in slot 3 now -> regular
        ] + [_card(i, chr(ord("A") + i)) for i in range(4, 8)]
        self.assertNotEqual(infer_deck(cards_a)["hash"], infer_deck(cards_b)["hash"])
