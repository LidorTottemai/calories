#!/usr/bin/env python3
"""
Benchmark: gpt-4o-mini vs claude-sonnet-4-6 for Israeli food nutrition analysis.
Run: python benchmark.py

Set ANTHROPIC_API_KEY in .env before running.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI
import anthropic

load_dotenv()

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

# (meal description, verified_calories, verified_protein_g, source)
TEST_CASES = [
    ("70 גרם שניצל",                                    168,  15.4, "USDA: chicken schnitzel 70g"),
    ("גביע לאבנה 5% של גד",                             200,  21.3, "גד label: 250g × 8.5g/100g"),
    ("3 ביצים מקושקשות עם כפית שמן זית",               270,  19.5, "3 large eggs + 5ml oil"),
    ("כוס קוואקר עם כוס חלב 1%",                       280,  12.0, "80g oats + 240ml 1% milk"),
    ("כרע עוף + 2 שיפודי פרגית + 6 תפודים קטנים",    1100,  88.0, "ChatGPT midpoint estimate"),
    ("100 גרם חזה עוף על האש",                          165,  31.0, "USDA: grilled chicken breast"),
    ("פיתה עם חומוס 3 כפות וסלט ירקות",               420,  13.0, "pita 65g + hummus 75g + veg"),
]

SYSTEM_PROMPT = """You are a precise nutrition calculator. The user describes a meal in Hebrew or English.

STEP 1 — Break the meal into individual items and estimate each one separately.
STEP 2 — Sum all items to get the totals.

Typical Israeli/Middle-Eastern reference portions:
- כרע עוף / chicken leg (bone-in, grilled): ~280g raw → ~220 kcal, 28g protein
- שיפוד פרגית / chicken skewer: ~120g meat → ~200 kcal, 25g protein
- תפוח אדמה קטן / small potato: ~90g → 70 kcal, 1.5g protein, 16g carbs
- פיתה / pita: ~65g → 170 kcal, 5g protein, 35g carbs
- גביע לאבנה / labneh container (גד, תנובה): standard = 250g → ~200 kcal, 21g protein, 5g carbs
- לאבנה 5% / labneh 5% fat (100g): 80 kcal, 8.5g protein, 2g carbs
- ביצה / egg (large): 75 kcal, 6.5g protein, 0.5g carbs
- פריכייה / rice cake: ~35 kcal, 0.7g protein, 7g carbs
- חזה עוף / chicken breast (100g grilled): 165 kcal, 31g protein
- חומוס / hummus (100g): 165 kcal, 8g protein, 14g carbs

Respond ONLY with a valid JSON object:
{
  "items": [{"name": "...", "calories": 0, "protein_g": 0.0, "carbs_g": 0.0}],
  "calories": 0,
  "protein_g": 0.0,
  "carbs_g": 0.0,
  "has_fiber": false,
  "description": "..."
}
Rules:
- List EVERY ingredient separately.
- "גביע" = full standard container (250g for dairy).
- Use exact quantities when given."""


@dataclass
class Result:
    model: str
    calories: int
    protein_g: float
    latency_ms: int
    error: str | None = None


async def run_openai(meal: str, model: str) -> Result:
    client = AsyncOpenAI(api_key=OPENAI_KEY)
    t0 = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": meal},
            ],
            temperature=0,
        )
        data = json.loads(resp.choices[0].message.content)
        ms = int((time.monotonic() - t0) * 1000)
        if "error" in data:
            return Result(model, 0, 0.0, ms, "cannot_identify")
        return Result(model, int(data["calories"]), float(data["protein_g"]), ms)
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return Result(model, 0, 0.0, ms, str(e)[:60])


async def run_claude(meal: str, model: str) -> Result:
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)
    t0 = time.monotonic()
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": meal}],
        )
        text = resp.content[0].text.strip()
        # Claude might wrap in ```json ... ``` — strip it
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        ms = int((time.monotonic() - t0) * 1000)
        if "error" in data:
            return Result(model, 0, 0.0, ms, "cannot_identify")
        return Result(model, int(data["calories"]), float(data["protein_g"]), ms)
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return Result(model, 0, 0.0, ms, str(e)[:60])


def pct_error(got: float, expected: float) -> str:
    if expected == 0:
        return "N/A"
    err = (got - expected) / expected * 100
    sign = "+" if err > 0 else ""
    return f"{sign}{err:.0f}%"


async def main():
    models = [
        ("gpt-4o-mini",        run_openai),
        ("claude-sonnet-4-6",  run_claude),
    ]

    cal_errors = {m: [] for m, _ in models}
    prot_errors = {m: [] for m, _ in models}

    for meal, exp_cal, exp_prot, source in TEST_CASES:
        print(f"\n{'─'*70}")
        print(f"🍽  {meal}")
        print(f"    ✅ Expected: {exp_cal} kcal | {exp_prot}g protein  ({source})")
        print()

        tasks = [fn(meal, model) for model, fn in models]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r.error:
                print(f"    ❌ {r.model:<25} ERROR: {r.error}")
                continue
            c_err = pct_error(r.calories, exp_cal)
            p_err = pct_error(r.protein_g, exp_prot)
            cal_errors[r.model].append(abs((r.calories - exp_cal) / exp_cal * 100))
            prot_errors[r.model].append(abs((r.protein_g - exp_prot) / exp_prot * 100))
            print(f"    {r.model:<25} {r.calories:>4} kcal ({c_err:>5}) | "
                  f"{r.protein_g:>5.1f}g protein ({p_err:>5}) | {r.latency_ms}ms")

    print(f"\n{'═'*70}")
    print("📊 SUMMARY — mean absolute % error (lower = better)")
    print(f"{'Model':<25} {'Calories MAE':>14} {'Protein MAE':>14}")
    print(f"{'─'*55}")
    for model, _ in models:
        c = cal_errors[model]
        p = prot_errors[model]
        c_mae = f"{sum(c)/len(c):.1f}%" if c else "N/A"
        p_mae = f"{sum(p)/len(p):.1f}%" if p else "N/A"
        print(f"{model:<25} {c_mae:>14} {p_mae:>14}")


if __name__ == "__main__":
    asyncio.run(main())
