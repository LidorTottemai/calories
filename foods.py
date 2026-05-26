from __future__ import annotations

# (kcal_per_100g, protein_g_per_100g, carbs_g_per_100g)
FOODS: dict[str, tuple[float, float, float]] = {
    # Protein powders
    "whey_protein_powder":         (375, 75.0,  6.0),
    "casein_protein_powder":       (360, 80.0,  4.0),
    # Poultry
    "chicken_breast_grilled":      (165, 31.0,  0.0),
    "chicken_breast_raw":          (120, 23.0,  0.0),
    "chicken_leg_grilled":         (189, 26.0,  0.0),
    "chicken_skewer_grilled":      (175, 27.0,  0.0),
    "chicken_schnitzel":           (230, 17.0, 12.0),
    "turkey_breast_grilled":       (135, 30.0,  0.0),
    "turkey_schnitzel":            (210, 18.0, 11.0),
    "shawarma_chicken":            (200, 22.0,  3.0),
    # Beef & Lamb
    "ground_beef_85lean":          (215, 26.0,  0.0),
    "entrecote_grilled":           (271, 26.0,  0.0),
    "lamb_chop_grilled":           (294, 25.0,  0.0),
    "beef_kebab":                  (249, 17.0,  9.0),
    # Fish
    "tuna_canned_water":           ( 96, 22.0,  0.0),
    "tuna_canned_oil":             (198, 29.0,  0.0),
    "salmon_grilled":              (208, 20.0,  0.0),
    "salmon_raw":                  (179, 19.9,  0.0),
    "sardines_canned":             (208, 24.6,  0.0),
    "smoked_salmon":               (117, 18.3,  0.0),
    "tilapia_grilled":             (128, 26.0,  0.0),
    # Eggs — per 100g ≈ 2 large eggs
    "egg_whole":                   (143, 13.0,  0.7),
    "egg_white":                   ( 52, 10.9,  0.7),
    # Dairy
    "labneh_5pct":                 ( 80,  8.5,  2.0),
    "labneh_9pct":                 (130,  8.0,  2.5),
    "cottage_cheese_5pct":         ( 98,  9.5,  3.5),
    "cottage_cheese_9pct":         (120,  9.0,  3.0),
    "yellow_cheese":               (357, 25.0,  1.5),
    "bulgarian_cheese_5pct":       (120, 14.0,  2.0),
    "bulgarian_cheese_9pct":       (167, 13.0,  1.5),
    "feta_cheese":                 (264, 14.2,  4.1),
    "mozzarella":                  (280, 18.0,  2.2),
    "cream_cheese":                (342,  5.9,  4.1),
    "milk_1pct":                   ( 42,  3.4,  4.9),
    "milk_3pct":                   ( 60,  3.2,  4.8),
    "yogurt_plain_1pct":           ( 57,  5.0,  6.0),
    "yogurt_plain_3pct":           ( 68,  4.5,  5.5),
    "sour_cream_15pct":            (164,  2.7,  4.0),
    # Grains & Bread
    "white_rice_cooked":           (130,  2.7, 28.0),
    "brown_rice_cooked":           (123,  2.7, 25.6),
    "oatmeal_dry":                 (379, 13.0, 67.0),
    "oatmeal_cooked":              ( 71,  2.5, 12.0),
    "white_pita":                  (265,  8.7, 54.0),
    "whole_wheat_pita":            (247, 10.0, 49.0),
    "white_bread":                 (265,  9.0, 51.0),
    "whole_wheat_bread":           (247, 11.0, 47.0),
    "baguette":                    (274,  9.5, 55.0),
    "pasta_cooked":                (131,  5.0, 25.0),
    "pasta_dry":                   (358, 13.0, 70.0),
    "couscous_cooked":             (112,  3.8, 23.0),
    "quinoa_cooked":               (120,  4.4, 21.0),
    "corn_tortilla":               (218,  5.7, 46.0),
    "wheat_tortilla":              (304,  9.0, 52.0),
    # Starchy vegetables
    "potato_cooked":               ( 77,  2.0, 17.0),
    "sweet_potato_cooked":         ( 86,  1.6, 20.0),
    "corn_cooked":                 ( 96,  3.4, 21.0),
    "butternut_squash_cooked":     ( 45,  1.0, 10.0),
    # Non-starchy vegetables
    "broccoli":                    ( 34,  2.8,  7.0),
    "cucumber":                    ( 15,  0.7,  3.6),
    "tomato":                      ( 18,  0.9,  3.9),
    "carrot":                      ( 41,  0.9, 10.0),
    "spinach":                     ( 23,  2.9,  3.6),
    "mushroom":                    ( 22,  3.1,  3.3),
    "onion":                       ( 40,  1.1,  9.3),
    "bell_pepper":                 ( 31,  1.0,  6.0),
    "zucchini":                    ( 17,  1.2,  3.1),
    "eggplant":                    ( 25,  1.0,  6.0),
    "cabbage":                     ( 25,  1.3,  5.8),
    "lettuce":                     ( 15,  1.4,  2.9),
    # Fruits
    "banana":                      ( 89,  1.1, 23.0),
    "apple":                       ( 52,  0.3, 14.0),
    "orange":                      ( 47,  0.9, 12.0),
    "dates_fresh":                 (282,  2.5, 75.0),
    "strawberry":                  ( 32,  0.7,  7.7),
    "watermelon":                  ( 30,  0.6,  7.6),
    "grapes":                      ( 67,  0.6, 17.0),
    "mango":                       ( 60,  0.8, 15.0),
    "pear":                        ( 57,  0.4, 15.0),
    # Legumes
    "hummus":                      (166,  7.9, 14.0),
    "lentils_cooked":              (116,  9.0, 20.0),
    "chickpeas_cooked":            (164,  8.9, 27.0),
    "falafel":                     (333, 13.0, 31.0),
    "edamame":                     (122, 11.0, 10.0),
    # Fats & Oils
    "olive_oil":                   (884,  0.0,  0.0),
    "avocado":                     (160,  2.0,  9.0),
    "tahini":                      (595, 17.0, 21.0),
    "peanut_butter":               (588, 25.0, 22.0),
    "almonds":                     (579, 21.0, 22.0),
    "walnuts":                     (654, 15.0, 14.0),
    "cashews":                     (553, 18.0, 30.0),
    "sunflower_seeds":             (584, 20.8, 20.0),
    # Snacks & sweets
    "rice_cake":                   (387,  7.3, 81.0),
    "granola":                     (471,  9.0, 62.0),
    "dark_chocolate_70pct":        (598,  7.8, 46.0),
    "milk_chocolate":              (535,  7.7, 59.0),
    "halva":                       (523, 13.0, 57.0),
    "protein_bar_generic":         (380, 30.0, 35.0),
    # Condiments
    "ketchup":                     (101,  1.3, 25.0),
    "mayo":                        (680,  0.9,  2.0),
    "honey":                       (304,  0.3, 82.0),
    "soy_sauce":                   ( 53,  8.1,  5.0),
}

FOOD_KEYS_LIST = ", ".join(sorted(FOODS.keys()))


def lookup(food_key: str, amount_g: float) -> tuple[int, float, float] | None:
    """Return (calories, protein_g, carbs_g) scaled to amount_g, or None."""
    entry = FOODS.get(food_key)
    if not entry:
        return None
    factor = amount_g / 100.0
    return (round(entry[0] * factor), round(entry[1] * factor, 1), round(entry[2] * factor, 1))
