from unittest import TestCase

from apis.utils.variants import is_variant_unlocked, slot_active_variant


class TestSlotActiveVariant(TestCase):
    def test_slot_0_with_evolution_returns_evolution(self):
        self.assertEqual(slot_active_variant(0, True, False), "evolution")

    def test_slot_0_without_evolution_returns_none(self):
        self.assertIsNone(slot_active_variant(0, False, False))
        self.assertIsNone(slot_active_variant(0, False, True))

    def test_slot_1_with_hero_returns_hero(self):
        self.assertEqual(slot_active_variant(1, False, True), "hero")
        self.assertEqual(slot_active_variant(1, True, True), "hero")

    def test_slot_1_with_evo_only_returns_evolution(self):
        self.assertEqual(slot_active_variant(1, True, False), "evolution")

    def test_slot_1_with_neither_returns_none(self):
        self.assertIsNone(slot_active_variant(1, False, False))

    def test_slot_2_matches_slot_1_logic(self):
        self.assertEqual(slot_active_variant(2, False, True), "hero")
        self.assertEqual(slot_active_variant(2, True, False), "evolution")
        self.assertIsNone(slot_active_variant(2, False, False))

    def test_slots_3_to_7_always_none(self):
        for idx in range(3, 8):
            self.assertIsNone(slot_active_variant(idx, True, True))


class TestIsVariantUnlocked(TestCase):
    def test_no_variant_required_always_true(self):
        self.assertTrue(is_variant_unlocked(0, None))
        self.assertTrue(is_variant_unlocked(None, None))
        self.assertTrue(is_variant_unlocked(3, None))

    def test_none_evolution_level_means_nothing_unlocked(self):
        self.assertFalse(is_variant_unlocked(None, "evolution"))
        self.assertFalse(is_variant_unlocked(None, "hero"))

    def test_zero_evolution_level_means_nothing_unlocked(self):
        self.assertFalse(is_variant_unlocked(0, "evolution"))
        self.assertFalse(is_variant_unlocked(0, "hero"))

    def test_evolution_level_1_is_evo_only(self):
        self.assertTrue(is_variant_unlocked(1, "evolution"))
        self.assertFalse(is_variant_unlocked(1, "hero"))

    def test_evolution_level_2_is_hero_only(self):
        self.assertFalse(is_variant_unlocked(2, "evolution"))
        self.assertTrue(is_variant_unlocked(2, "hero"))

    def test_evolution_level_3_is_both(self):
        self.assertTrue(is_variant_unlocked(3, "evolution"))
        self.assertTrue(is_variant_unlocked(3, "hero"))
