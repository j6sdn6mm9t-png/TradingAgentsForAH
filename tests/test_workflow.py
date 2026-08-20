import json
from pathlib import Path
import unittest
from dataclasses import replace
from datetime import date

from ashare_research.data.demo import DemoDataProvider
from ashare_research.data.json_file import JsonFileDataProvider
from ashare_research.domain import CompanyQuality, ValuationView
from ashare_research.report import render_markdown
from ashare_research.workflow import ResearchWorkflow


class ResearchWorkflowTests(unittest.TestCase):
    def test_demo_run_builds_adaptive_company_research(self):
        state = ResearchWorkflow(DemoDataProvider()).run(
            "600519.SH", date(2026, 8, 18)
        )
        self.assertIsNotNone(state.blueprint)
        self.assertIsNotNone(state.valuation)
        self.assertIsNotNone(state.synthesis)
        self.assertEqual(state.trace[-1], "research:synthesis")
        self.assertIn("brand_channel", state.blueprint.selected_roles)
        self.assertEqual(
            set(state.blueprint.selected_roles), set(state.blueprint.role_rationales)
        )
        self.assertNotIn("position", json.dumps(state.to_dict(), ensure_ascii=False))
        compatible_state, synthesis = ResearchWorkflow(DemoDataProvider()).propagate(
            "600519.SH", "2026-08-18"
        )
        self.assertIs(synthesis, compatible_state.synthesis)

    def test_company_archetype_changes_specialist_and_horizon(self):
        consumer = ResearchWorkflow(DemoDataProvider()).run(
            "600519.SH", date(2026, 8, 18)
        )
        platform = ResearchWorkflow(DemoDataProvider()).run(
            "700.HK", date(2026, 8, 18)
        )
        self.assertEqual(platform.security.symbol, "00700.HK")
        self.assertIn("unit_economics", platform.blueprint.selected_roles)
        self.assertNotEqual(consumer.blueprint.horizon, platform.blueprint.horizon)
        self.assertNotEqual(
            consumer.blueprint.selected_roles, platform.blueprint.selected_roles
        )

    def test_explicit_empty_researcher_list_is_respected(self):
        state = ResearchWorkflow(DemoDataProvider(), analysts=[]).run(
            "600519.SH", date(2026, 8, 18)
        )
        self.assertEqual(state.analyst_reports, [])
        self.assertEqual(state.synthesis.confidence, 0.0)

    def test_safety_margin_changes_with_company_characteristics(self):
        consumer = ResearchWorkflow(DemoDataProvider()).run(
            "600519.SH", date(2026, 8, 18)
        )
        cyclical = ResearchWorkflow(DemoDataProvider()).run(
            "300750.SZ", date(2026, 8, 18)
        )
        self.assertLess(
            consumer.valuation.safety_margin_pct,
            cyclical.valuation.safety_margin_pct,
        )

    def test_st_status_becomes_research_risk_not_position_gate(self):
        class STProvider(DemoDataProvider):
            def get_snapshot(self, security, as_of):
                return replace(super().get_snapshot(security, as_of), is_st=True)

        state = ResearchWorkflow(STProvider()).run("600519.SH", date(2026, 8, 18))
        self.assertTrue(any("风险警示" in risk for risk in state.synthesis.risks))
        self.assertIsNotNone(state.valuation)

    def test_json_provider_uses_normalized_contract(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "research_data.json"
        state = ResearchWorkflow(JsonFileDataProvider(path)).run(
            "600519", date(2026, 8, 18)
        )
        self.assertEqual(state.snapshot.name, "贵州茅台")
        known = {item.evidence_id for item in state.evidence}
        for report in state.analyst_reports:
            self.assertTrue(set(report.evidence_ids) <= known)
        self.assertTrue(set(state.valuation_context.evidence_ids) <= known)

    def test_future_snapshot_is_rejected(self):
        class FutureProvider(DemoDataProvider):
            def get_snapshot(self, security, as_of):
                return replace(super().get_snapshot(security, as_of), as_of=date(2026, 8, 19))

        with self.assertRaisesRegex(ValueError, "future market snapshot"):
            ResearchWorkflow(FutureProvider()).run("600519.SH", date(2026, 8, 18))

    def test_provider_without_evidence_is_rejected(self):
        class EmptyEvidenceProvider(DemoDataProvider):
            def get_evidence(self, security, as_of):
                return []

        with self.assertRaisesRegex(ValueError, "no auditable evidence"):
            ResearchWorkflow(EmptyEvidenceProvider()).run(
                "600519.SH", date(2026, 8, 18)
            )

    def test_future_evidence_observation_is_rejected(self):
        class FutureObservationProvider(DemoDataProvider):
            def get_evidence(self, security, as_of):
                evidence = super().get_evidence(security, as_of)
                evidence[0] = replace(evidence[0], observed_at=date(2026, 8, 19))
                return evidence

        with self.assertRaisesRegex(ValueError, "future observation"):
            ResearchWorkflow(FutureObservationProvider()).run(
                "600519.SH", date(2026, 8, 18)
            )

    def test_unknown_symbol_fails_closed_on_quality_and_valuation(self):
        state = ResearchWorkflow(DemoDataProvider()).run(
            "000001.SZ", date(2026, 8, 18)
        )
        self.assertEqual(state.synthesis.company_quality, CompanyQuality.INSUFFICIENT)
        self.assertEqual(state.valuation.view, ValuationView.INSUFFICIENT)
        self.assertIsNone(state.valuation.ideal_buy_below)

    def test_integrated_report_has_required_questions_without_role_log(self):
        state = ResearchWorkflow(DemoDataProvider()).run(
            "600519.SH", date(2026, 8, 18)
        )
        report = render_markdown(state)
        for heading in (
            "核心结论与主要矛盾",
            "商业模式与价值驱动",
            "增长点与增长势头",
            "股价反映了多少",
            "估值、安全边际与价格区间",
        ):
            self.assertIn(heading, report)
        for legacy in ("分析师团队", "研究团队辩论", "风险委员会", "目标仓位"):
            self.assertNotIn(legacy, report)
        self.assertIn("理想买入上限", report)
        self.assertIn("卖出复核", report)


if __name__ == "__main__":
    unittest.main()
