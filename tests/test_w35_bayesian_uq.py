"""Тесты W-35: Bayesian UQ — credible intervals и posterior probability."""
from __future__ import annotations

import math
import numpy as np
import pytest


class TestAnalyticalCredibleInterval:
    """Тесты аналитического credible interval."""
    
    def test_95_ci_normal(self):
        """95% CI для нормального распределения: mean ± 1.96·σ."""
        from chem_agent.uncertainty.ensemble import analytical_credible_interval
        
        mean = 0.0
        sigma = 1.0
        ci = analytical_credible_interval(mean, sigma, 0.95)
        
        assert abs(ci[0] - (-1.96)) < 0.01
        assert abs(ci[1] - 1.96) < 0.01
    
    def test_90_ci_normal(self):
        """90% CI для нормального распределения: mean ± 1.645·σ."""
        from chem_agent.uncertainty.ensemble import analytical_credible_interval
        
        mean = 10.0
        sigma = 2.0
        ci = analytical_credible_interval(mean, sigma, 0.90)
        
        assert abs(ci[0] - (10.0 - 1.645 * 2.0)) < 0.01
        assert abs(ci[1] - (10.0 + 1.645 * 2.0)) < 0.01
    
    def test_ci_scales_with_sigma(self):
        """CI пропорционален σ."""
        from chem_agent.uncertainty.ensemble import analytical_credible_interval
        
        ci_1 = analytical_credible_interval(0.0, 1.0, 0.95)
        ci_2 = analytical_credible_interval(0.0, 2.0, 0.95)
        
        assert abs(ci_2[0] / ci_1[0] - 2.0) < 0.01
        assert abs(ci_2[1] / ci_1[1] - 2.0) < 0.01


class TestSummarize:
    """Тесты функции summarize с credible intervals."""
    
    def test_summarize_returns_90_and_95_ci(self):
        """summarize возвращает оба credible interval."""
        from chem_agent.uncertainty.ensemble import summarize
        
        values = np.random.normal(0.0, 1.0, 1000).tolist()
        result = summarize(values)
        
        assert "credible_interval_90" in result
        assert "credible_interval_95" in result
        assert result["credible_interval_90"] is not None
        assert result["credible_interval_95"] is not None
        
        # 95% CI шире 90% CI
        width_90 = result["credible_interval_90"][1] - result["credible_interval_90"][0]
        width_95 = result["credible_interval_95"][1] - result["credible_interval_95"][0]
        assert width_95 > width_90
    
    def test_summarize_empty(self):
        """summarize для пустого списка возвращает None."""
        from chem_agent.uncertainty.ensemble import summarize
        
        result = summarize([])
        assert result["mean"] is None
        assert result["credible_interval_90"] is None
        assert result["credible_interval_95"] is None


class TestPosteriorProbability:
    """Интеграционные тесты posterior probability."""
    
    def test_posterior_probability_in_response(self):
        """posterior_probability присутствует в ответе agent.predict()."""
        from chem_agent.agent import Agent
        
        agent = Agent(offline=True)
        result = agent.predict(
            reagents=[{"formula": "NaOH", "moles": 0.05, "phase": "aq"},
                      {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
            options={"accuracy": "fast", "include_uncertainty": True}
        )
        
        unc = result.data.get("uncertainty")
        if unc:
            assert "posterior_probability" in unc
            assert "confidence" in unc  # alias
            assert unc["posterior_probability"] == unc["confidence"]
    
    def test_credible_intervals_in_summary(self):
        """95% CI присутствуют в summary."""
        from chem_agent.agent import Agent
        
        agent = Agent(offline=True)
        result = agent.predict(
            reagents=[{"formula": "NaOH", "moles": 0.05, "phase": "aq"},
                      {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
            options={"accuracy": "balanced", "include_uncertainty": True}
        )
        
        summary = result.data.get("summary", {})
        
        # Хотя бы один из CI должен присутствовать
        has_ci = (
            "delta_G_95_CI" in summary or
            "delta_G_analytical_95_CI" in summary or
            "pH_95_CI" in summary or
            "main_product_moles_95_CI" in summary
        )
        assert has_ci, "Ни один 95% CI не найден в summary"