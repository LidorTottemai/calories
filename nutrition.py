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


_SYSTEM_PROMPT = """You are a nutrition analysis assistant. The user describes food they ate, in Hebrew or English.
Your job is to estimate the nutritional content of the meal.

Respond ONLY with a valid JSON object with exactly these keys:
{
  "calories": <integer, total kcal>,
  "protein_g": <number, grams of protein, one decimal place>,
  "carbs_g": <number, grams of carbohydrates, one decimal place>,
  "has_fiber": <boolean, true if the meal contains meaningful dietary fiber>,
  "description": "<short English summary of the food, max 60 chars>"
}

Rules:
- If amounts are not specified, assume a typical single serving.
- Round calories to the nearest whole number.
- has_fiber is true for: vegetables, fruits, legumes, whole grains, nuts, seeds, oats.
- has_fiber is false for: white rice, white bread, plain pasta, meat, poultry, fish, dairy, eggs, refined sugar, oils.
- If the meal contains BOTH fiber and non-fiber items, has_fiber is true.
- If you cannot identify the food at all, return: {"error": "cannot_identify"}"""


@dataclass
class NutritionResult:
    calories: int
    protein_g: float
    carbs_g: float
    has_fiber: bool
    raw_description: str


async def analyze_meal(user_text: str) -> NutritionResult:
    response = await _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0.2,
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
