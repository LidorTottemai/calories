import json
from dataclasses import dataclass
from openai import AsyncOpenAI
import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


_SYSTEM_PROMPT = """You are a precise nutrition calculator. The user describes a meal in Hebrew or English.

STEP 1 — Break the meal into individual items and estimate each one separately.
STEP 2 — Sum all items to get the totals.

Typical Israeli/Middle-Eastern reference portions (use these when no quantity is given):
- כרע עוף / chicken leg (bone-in, grilled): ~280g raw → ~220 kcal, 28g protein
- שיפוד פרגית / chicken skewer: ~120g meat → ~200 kcal, 25g protein
- שיפוד אנטריקוט / entrecote skewer: ~120g → ~300 kcal, 24g protein
- תפוח אדמה קטן / small potato: ~90g → 70 kcal, 1.5g protein, 16g carbs
- בטטה / sweet potato (100g): 90 kcal, 2g protein, 20g carbs
- פיתה / pita: ~65g → 170 kcal, 5g protein, 35g carbs
- אורז מבושל / cooked rice (cup): ~180g → 200 kcal, 4g protein, 44g carbs
- גביע לאבנה / labneh container (גד, תנובה etc.): standard = 250g → ~200 kcal, 21g protein, 5g carbs
- לאבנה 5% / labneh 5% fat (100g): 80 kcal, 8.5g protein, 2g carbs
- גבינה בולגרית 5% / Bulgarian cheese 5% (100g): 120 kcal, 14g protein, 2g carbs
- קוטג' / cottage cheese (container 250g): 200 kcal, 22g protein, 6g carbs
- ביצה / egg (large): 75 kcal, 6.5g protein, 0.5g carbs
- פריכייה / rice cake (one piece): ~35 kcal, 0.7g protein, 7g carbs

Respond ONLY with a valid JSON object with exactly these keys:
{
  "items": [
    {"name": "<item name>", "calories": <int>, "protein_g": <float>, "carbs_g": <float>}
  ],
  "calories": <integer, SUM of all items>,
  "protein_g": <float, SUM, one decimal>,
  "carbs_g": <float, SUM, one decimal>,
  "has_fiber": <boolean>,
  "description": "<short English summary, max 60 chars>"
}

Rules:
- ALWAYS list every ingredient as a separate item — never skip one.
- When a quantity is given (e.g. "20 גרם"), use it exactly.
- When no quantity is given, use the reference portions above or a realistic home/restaurant serving.
- "גביע" = a full standard container (usually 250g for dairy). Never assume a small spoonful.
- has_fiber is true if the meal contains vegetables, fruit, legumes, whole grains, nuts, or seeds.
- If you cannot identify the food at all, return: {"error": "cannot_identify"}"""


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

    return NutritionResult(
        calories=int(data["calories"]),
        protein_g=float(data["protein_g"]),
        carbs_g=float(data["carbs_g"]),
        has_fiber=bool(data["has_fiber"]),
        raw_description=str(data["description"]),
    )
