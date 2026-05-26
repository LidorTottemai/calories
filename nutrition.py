import json
from dataclasses import dataclass
from openai import AsyncOpenAI
import config
from foods import FOOD_KEYS_LIST, lookup

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_SYSTEM_PROMPT = f"""You are a precise nutrition calculator. The user describes a meal in Hebrew or English.

STEP 1 — Break the meal into individual items and estimate each one separately.
STEP 2 — Sum all items to get the totals.

Known food keys (assign one when it exactly matches the ingredient):
{FOOD_KEYS_LIST}

Typical Israeli/Middle-Eastern reference portions (use these when no quantity is given):
- כרע עוף / chicken leg (bone-in, grilled): ~280g raw → amount_g=220 cooked
- שיפוד פרגית / chicken skewer: amount_g=120
- שיפוד אנטריקוט / entrecote skewer: amount_g=120
- תפוח אדמה קטן / small potato: amount_g=90
- בטטה / sweet potato: amount_g=100
- פיתה / pita: amount_g=65
- אורז מבושל / cooked rice (cup): amount_g=180
- גביע לאבנה / labneh container (גד, תנובה etc.): amount_g=250
- קוטג' / cottage cheese container: amount_g=250
- ביצה / egg (large): amount_g=50
- פריכייה / rice cake (one piece): amount_g=9

Respond ONLY with a valid JSON object with exactly these keys:
{{
  "items": [
    {{
      "name": "<item name>",
      "food_key": "<key from the known list above, or null>",
      "amount_g": <estimated grams as float>,
      "calories": <int estimate>,
      "protein_g": <float estimate>,
      "carbs_g": <float estimate>
    }}
  ],
  "calories": <integer, SUM of all items>,
  "protein_g": <float, SUM, one decimal>,
  "carbs_g": <float, SUM, one decimal>,
  "has_fiber": <boolean>,
  "description": "<short English summary, max 60 chars>"
}}

Rules:
- ALWAYS list every ingredient as a separate item — never skip one.
- When a quantity is given (e.g. "20 גרם"), use it exactly as amount_g.
- When no quantity is given, use the reference portions above or a realistic home/restaurant serving.
- "גביע" = a full standard container (usually 250g for dairy). Never assume a small spoonful.
- Set food_key only when you are confident it exactly matches; otherwise set null.
- has_fiber is true if the meal contains vegetables, fruit, legumes, whole grains, nuts, or seeds.
- has_fiber is false for: white rice, white bread, meat, dairy, eggs, refined sugar.
- If you cannot identify the food at all, return: {{"error": "cannot_identify"}}"""


@dataclass
class NutritionResult:
    calories: int
    protein_g: float
    carbs_g: float
    has_fiber: bool
    raw_description: str


_MOTIVATION_SYSTEM_PROMPT = """אתה מאמן כושר ותזונה אישי בעברית — חם, אנושי, ומעצים.
כתוב הודעת עידוד קצרה (2-4 משפטים) בהתאם למצב שמתואר.
השתמש באימוג'ים בצורה טבעית. היה מגוון — אל תחזור על אותן פתיחות.
הגב עם טקסט ההודעה בלבד, ללא ציטוטים או הסברים."""


async def generate_motivation(
    hour: int,
    goal_cal: int,
    goal_protein: float,
    consumed_cal: int = 0,
    consumed_protein: float = 0.0,
) -> str:
    if hour == 8:
        user_content = (
            f"בוקר טוב! היום היעד הוא {goal_cal:,} קלוריות ו-{goal_protein:.0f} גר' חלבון. "
            "כתוב הודעת בוקר מעוררת ומוטיבציונית — בלי נתונים, רק עידוד."
        )
    else:
        pct_cal = round(consumed_cal / goal_cal * 100) if goal_cal > 0 else 0
        pct_protein = round(consumed_protein / goal_protein * 100) if goal_protein > 0 else 0
        over_cal = consumed_cal - goal_cal

        if hour == 12:
            time_ctx = "אמצע היום (12:00)"
        elif hour == 19:
            time_ctx = "ערב (19:00)"
        else:
            time_ctx = "סוף היום (23:00)"

        user_content = (
            f"השעה: {time_ctx}\n"
            f"קלוריות: {consumed_cal:,} מתוך יעד {goal_cal:,} ({pct_cal}%)"
            + (f" — חריגה של {over_cal:,}" if over_cal > 0 else "") + "\n"
            f"חלבון: {consumed_protein:.0f}g מתוך {goal_protein:.0f}g ({pct_protein}%)\n\n"
            "כתוב הודעת עידוד מותאמת אישית. "
            "חריגה של פחות מ-5% היא לגמרי בסדר — אל תגזים בביקורת. "
            "אם לא נרשמו ארוחות — עודד לרשום."
        )

    response = await _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _MOTIVATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.9,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


async def analyze_meal(user_text: str) -> NutritionResult:
    response = await _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
    )

    data = json.loads(response.choices[0].message.content)

    if "error" in data:
        raise ValueError("cannot_identify")

    # Override AI estimates with DB values for known food_keys
    for item in data.get("items", []):
        food_key = item.get("food_key")
        amount_g = item.get("amount_g")
        if food_key and amount_g:
            override = lookup(food_key, float(amount_g))
            if override:
                item["calories"], item["protein_g"], item["carbs_g"] = override

    # Recalculate totals from (possibly overridden) items
    items = data.get("items", [])
    if items:
        data["calories"] = sum(int(i.get("calories", 0)) for i in items)
        data["protein_g"] = round(sum(float(i.get("protein_g", 0)) for i in items), 1)
        data["carbs_g"] = round(sum(float(i.get("carbs_g", 0)) for i in items), 1)

    return NutritionResult(
        calories=int(data["calories"]),
        protein_g=float(data["protein_g"]),
        carbs_g=float(data["carbs_g"]),
        has_fiber=bool(data["has_fiber"]),
        raw_description=str(data["description"]),
    )
