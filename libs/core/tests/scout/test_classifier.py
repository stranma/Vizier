"""Tests for Scout classifier."""

from __future__ import annotations

from vizier.core.models.spec import Spec, SpecFrontmatter
from vizier.core.scout.classifier import ScoutClassifier, ScoutDecision


def _make_spec(spec_id: str, content: str) -> Spec:
    return Spec(frontmatter=SpecFrontmatter(id=spec_id), content=content)


class TestScoutClassifier:
    def test_research_keywords_trigger_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("001-add-auth", "Add authentication to the application")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_implement_keyword_triggers_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("002-impl", "Implement a caching layer for the API")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_integrate_keyword_triggers_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("003-integrate", "Integrate Stripe payment processing")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_new_feature_triggers_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("004-new", "New dashboard for monitoring")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_fix_keyword_triggers_skip(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("005-fix-bug", "Fix the login timeout issue")
        assert classifier.classify(spec) == ScoutDecision.SKIP

    def test_refactor_keyword_triggers_skip(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("006-refactor", "Refactor the database module")
        assert classifier.classify(spec) == ScoutDecision.SKIP

    def test_rename_keyword_triggers_skip(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("007-rename", "Rename the User model fields")
        assert classifier.classify(spec) == ScoutDecision.SKIP

    def test_typo_keyword_triggers_skip(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("008-typo", "Fix typo in documentation")
        assert classifier.classify(spec) == ScoutDecision.SKIP

    def test_ambiguous_defaults_to_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("009-mystery", "Do something with the data pipeline")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_mixed_keywords_research_wins(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("010-mixed", "Add new logging and fix the output format")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH

    def test_empty_content_defaults_to_research(self) -> None:
        classifier = ScoutClassifier()
        spec = _make_spec("011-empty", "")
        assert classifier.classify(spec) == ScoutDecision.RESEARCH
