import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from budgetbot.classify import classify, classify_all, normalise_name
from budgetbot.config import Settings
from budgetbot.messages import Pace, days_left, transaction_alert
from budgetbot.runner import in_quiet_hours, months_to_fetch
from budgetbot.store import Store

TODAY = date(2026, 11, 14)
TZ = ZoneInfo("Asia/Jerusalem")


def rec(**over):
    base = dict(
        transactionId="t1", transactionDate="2026-11-10T00:00:00.000Z",
        businessName="מיקה מודיעין", amount=466.0, isIncome=False, isExcluded=False,
        sourceType="creditCard", cashflowDate="2026-11",
        actualType="variable", categoryLabel="רכב",
    )
    base.update(over)
    return base


class TestClassify(unittest.TestCase):
    def test_keeps_an_ordinary_variable_charge(self):
        t = classify(rec(), TODAY)
        self.assertIsNotNone(t)
        self.assertFalse(t.is_fixed)
        self.assertEqual(t.bucket, "רכב")
        self.assertEqual(t.shekels, 466)

    def test_drops_future_dated_standing_orders(self):
        # The feed carries scheduled charges days ahead; counting them would
        # report money that has not left the account yet.
        self.assertIsNone(classify(rec(transactionDate="2026-11-22T00:00:00.000Z"), TODAY))
        self.assertIsNotNone(classify(rec(transactionDate="2026-11-14T00:00:00.000Z"), TODAY))

    def test_drops_income_and_excluded(self):
        self.assertIsNone(classify(rec(isIncome=True), TODAY))
        self.assertIsNone(classify(rec(isExcluded=True), TODAY))

    def test_drops_aggregated_card_bill_in_checking_account(self):
        self.assertIsNone(classify(
            rec(businessName="מסטרקרד", sourceType="checkingAccount"), TODAY))
        # The same name on a card row is a real purchase, not a settlement.
        self.assertIsNotNone(classify(
            rec(businessName="מסטרקרד", sourceType="creditCard"), TODAY))

    def test_drops_savings_deposits(self):
        self.assertIsNone(classify(
            rec(businessName="אתר קרנות", categoryLabel="__saving-hidden-category__"), TODAY))

    def test_household_overrides_beat_riseup(self):
        t = classify(rec(businessName="תפארת האחוזה", amount=4300,
                         actualType="variable", categoryLabel="אחר"), TODAY)
        self.assertTrue(t.is_fixed)
        self.assertEqual(t.bucket, "")

    def test_unknown_category_falls_into_contingency(self):
        t = classify(rec(categoryLabel="משהו חדש"), TODAY)
        self.assertEqual(t.bucket, "בלת״ם ואירועים")

    def test_merchant_name_whitespace_is_collapsed(self):
        self.assertEqual(normalise_name("APPLE.COM/BILL    CORK   IE"),
                         "APPLE.COM/BILL CORK IE")

    def test_rejects_junk(self):
        self.assertIsNone(classify(rec(amount=0), TODAY))
        self.assertIsNone(classify(rec(amount=-5), TODAY))
        self.assertIsNone(classify(rec(transactionId=""), TODAY))
        self.assertIsNone(classify(rec(businessName="   "), TODAY))


class TestPacing(unittest.TestCase):
    def test_days_left_counts_today(self):
        self.assertEqual(days_left(date(2026, 11, 14)), 17)
        self.assertEqual(days_left(date(2026, 11, 30)), 1)

    def test_marker_tracks_expected_spend(self):
        half = date(2026, 11, 15)  # 15/30 of the month
        self.assertEqual(Pace(900, 2000, half).marker(), "✅")
        self.assertEqual(Pace(1400, 2000, half).marker(), "⚠️")
        self.assertEqual(Pace(2100, 2000, half).marker(), "🔴")

    def test_projection_extrapolates_the_rate(self):
        self.assertAlmostEqual(Pace(1000, 2000, date(2026, 11, 15)).projection, 2000, places=0)


class TestAlert(unittest.TestCase):
    def test_message_has_the_shape_the_household_asked_for(self):
        txn = classify(rec(), TODAY)
        text = transaction_alert(txn, spent=1841, today=TODAY)
        self.assertIn("מיקה מודיעין · 466 ₪", text)
        self.assertIn("קטגוריה: רכב", text)
        self.assertIn("עד כה החודש: 1,841 מתוך 2,000 ₪", text)
        self.assertIn("נותרו 159 ₪ · 17 ימים לסוף החודש", text)

    def test_overspend_is_named_not_hidden(self):
        txn = classify(rec(), TODAY)
        text = transaction_alert(txn, spent=2300, today=TODAY)
        self.assertIn("חריגה של 300 ₪", text)
        self.assertIn("🔴", text)


class TestQuietHours(unittest.TestCase):
    def setUp(self):
        self.s = Settings(quiet_start=(22, 30), quiet_end=(7, 30))

    def test_window_wraps_midnight(self):
        for hh, mm, quiet in [(23, 0, True), (2, 0, True), (7, 0, True),
                              (7, 30, False), (12, 0, False), (22, 29, False),
                              (22, 30, True)]:
            with self.subTest(time=f"{hh}:{mm}"):
                moment = datetime(2026, 11, 14, hh, mm, tzinfo=TZ)
                self.assertEqual(in_quiet_hours(moment, self.s), quiet)


class TestMonthsToFetch(unittest.TestCase):
    def test_only_current_month_mid_month(self):
        self.assertEqual(months_to_fetch(date(2026, 11, 14)), ["2026-11"])

    def test_also_previous_month_at_the_turn(self):
        self.assertEqual(months_to_fetch(date(2026, 11, 2)), ["2026-11", "2026-10"])

    def test_year_boundary(self):
        self.assertEqual(months_to_fetch(date(2026, 1, 1)), ["2026-01", "2025-12"])


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_new_then_quiet_on_resend(self):
        txns = classify_all([rec()], TODAY)
        self.assertEqual(len(self.store.upsert(txns, "now")), 1)
        self.assertEqual(self.store.upsert(txns, "now"), [])

    def test_settled_amount_reports_a_change(self):
        self.store.upsert(classify_all([rec(amount=100)], TODAY), "now")
        self.store.mark_alerted(["t1"])
        changes = self.store.upsert(classify_all([rec(amount=140)], TODAY), "now")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].kind, "amount")
        self.assertEqual(changes[0].previous, 100)
        self.assertEqual(self.store.bucket_totals("2026-11")["רכב"], 140)

    def test_fixed_is_kept_apart_and_never_announced(self):
        txns = classify_all([rec(businessName="תפארת האחוזה", amount=4300,
                                 transactionId="t9")], TODAY)
        self.assertEqual(self.store.upsert(txns, "now"), [])
        self.assertEqual(self.store.fixed_total("2026-11"), 4300)
        self.assertEqual(self.store.bucket_totals("2026-11"), {})

    def test_totals_recomputed_so_late_arrivals_self_correct(self):
        self.store.upsert(classify_all([
            rec(transactionId="a", amount=100),
            rec(transactionId="b", amount=250, transactionDate="2026-11-02T00:00:00.000Z"),
        ], TODAY), "now")
        self.assertEqual(self.store.bucket_totals("2026-11")["רכב"], 350)


if __name__ == "__main__":
    unittest.main()


class TestPersona(unittest.TestCase):
    def test_tone_follows_the_numbers(self):
        from budgetbot import persona
        half = date(2026, 11, 15)  # 15/30 of the month
        cases = [
            (900, 2000, persona.OK),
            (1400, 2000, persona.WARN),
            (2100, 2000, persona.OVER),
            (3200, 2000, persona.BLOWN),
        ]
        for spent, budget, expected in cases:
            with self.subTest(spent=spent):
                self.assertEqual(Pace(spent, budget, half).tone(), expected)

    def test_zero_budget_bucket_is_over_at_the_first_shekel(self):
        from budgetbot import persona
        day = date(2026, 11, 19)
        # The contingency line was zeroed, so anything landing there is unplanned.
        self.assertEqual(Pace(0, 0, day).tone(), persona.OK)
        self.assertEqual(Pace(0, 0, day).marker(), "✅")
        self.assertEqual(Pace(50, 0, day).tone(), persona.OVER)
        self.assertEqual(Pace(50, 0, day).marker(), "🔴")

    def test_budget_splits_still_total_ten_thousand(self):
        from budgetbot.config import VARIABLE_BUDGETS, VARIABLE_TOTAL
        self.assertEqual(VARIABLE_TOTAL, 10000)
        self.assertEqual(sum(VARIABLE_BUDGETS.values()), 10000)

    def test_pick_is_deterministic_but_varies(self):
        from budgetbot import persona
        bank = persona.LINES[persona.WARN]
        self.assertEqual(persona.pick(bank, "t1"), persona.pick(bank, "t1"))
        picks = {persona.pick(bank, f"t{i}") for i in range(60)}
        self.assertGreater(len(picks), 3, "the same line keeps coming back")

    def test_every_line_is_short_and_non_empty(self):
        from budgetbot import persona
        banks = list(persona.LINES.values()) + list(persona.DIGEST_OPENERS.values())
        for bank in banks:
            for line in bank:
                self.assertTrue(line.strip())
                self.assertLessEqual(len(line), 90, line)

    def test_no_duplicate_lines_anywhere(self):
        from budgetbot import persona
        everything = [l for bank in persona.LINES.values() for l in bank]
        everything += [l for bank in persona.DIGEST_OPENERS.values() for l in bank]
        dupes = {l for l in everything if everything.count(l) > 1}
        self.assertEqual(dupes, set())

    def test_each_register_has_enough_lines_to_not_repeat(self):
        from budgetbot import persona
        for state, bank in persona.LINES.items():
            with self.subTest(state=state):
                self.assertGreaterEqual(len(bank), 12, f"{state} is thin")
        for state, bank in persona.DIGEST_OPENERS.items():
            with self.subTest(digest=state):
                self.assertGreaterEqual(len(bank), 4, f"{state} is thin")

    def test_voice_is_appended_not_substituted(self):
        txn = classify(rec(), TODAY)
        plain = transaction_alert(txn, spent=1841, today=TODAY, speak=False)
        spoken = transaction_alert(txn, spent=1841, today=TODAY, speak=True)
        # Every figure survives; the character is added underneath.
        self.assertTrue(spoken.startswith(plain))
        self.assertIn("— מועלם", spoken)
        self.assertNotIn("— מועלם", plain)

    def test_overspend_draws_the_collector(self):
        from budgetbot import persona
        txn = classify(rec(), TODAY)
        spoken = transaction_alert(txn, spent=4000, today=TODAY)
        self.assertTrue(
            any(line in spoken for line in persona.LINES[persona.BLOWN]),
            "a 2x overspend should reach the loudest register",
        )

    def test_batch_speaks_at_the_worst_offender(self):
        from budgetbot import persona
        from budgetbot.messages import batched_alert
        calm = classify(rec(transactionId="a", categoryLabel="כלכלה"), TODAY)
        awful = classify(rec(transactionId="b", categoryLabel="פארמה"), TODAY)
        text = batched_alert([(calm, 100.0), (awful, 1200.0)], TODAY)
        self.assertTrue(any(line in text for line in persona.LINES[persona.BLOWN]))
