import json
from pathlib import Path

import httpx
import pytest

from app.classifier import classify_project, content_fingerprint


def test_author_declaration_attributed_tools():
    result = classify_project(
        "A personal task manager",
        "This app was built with Claude Code and Cursor.",
        "https://github.com/o/r",
    )
    assert result["evidence_level"] == "explicit"
    assert result["tools"] == ["Claude Code", "Cursor"]
    assert result["category"] == "生产力"
    assert result["method"] == "rules"


@pytest.mark.parametrize(
    "text,level",
    [
        ("An AI-powered image editor using OpenAI API.", "unknown"),
        ("Open this project in Cursor to get started.", "weak"),
        ("This app was not built with Cursor.", "unknown"),
        ("Learn to build apps with Cursor in this tutorial.", "weak"),
        ("This app was written by AI.", "explicit"),
        ("本项目使用 Cursor 开发。", "explicit"),
    ],
)
def test_build_evidence_is_not_ai_function_or_tool_mention(text, level):
    result = classify_project("", text, "https://github.com/o/r")
    assert result["evidence_level"] == level


def test_grounded_llm_claim_and_url():
    payload = {
        "category": "生产力",
        "kind": "application",
        "tools": ["Cursor"],
        "summary": "一个待办应用。",
        "evidence_level": "explicit",
        "evidence": [{"quote": "Built with Cursor.", "url": "https://untrusted.test"}],
    }
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
            )
        )
    )
    result = classify_project(
        "Todo",
        "Built with Cursor.",
        "https://github.com/o/r",
        "https://llm.test/v1",
        "secret",
        "test-model",
        client,
    )
    assert result["method"] == "llm"
    assert result["evidence"] == [
        {"quote": "Built with Cursor.", "url": "https://github.com/o/r"}
    ]


def test_llm_fabricated_evidence_cannot_promote_membership():
    payload = {
        "category": "内容创作",
        "kind": "application",
        "tools": ["Cursor"],
        "summary": "图片编辑器。",
        "evidence_level": "explicit",
        "evidence": [{"quote": "Built with Cursor."}],
    }
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
            )
        )
    )
    result = classify_project(
        "AI image editor",
        "Powered by an image model.",
        "https://github.com/o/r",
        "https://llm.test/v1",
        "secret",
        "test-model",
        client,
    )
    assert result["evidence_level"] == "unknown"
    assert result["tools"] == []
    assert result["evidence"] == []


def test_llm_invalid_output_and_timeout_are_labeled_fallbacks():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"choices": [{"message": {"content": "not json"}}]}
            )
        )
    )
    result = classify_project(
        "Notes",
        "Built with Codex.",
        "https://github.com/o/r",
        "https://llm.test/v1",
        "secret",
        "model",
        client,
    )
    assert result["method"] == "rules"
    assert result["fallback_reason"]
    assert result["tools"] == ["Codex"]
    assert "secret" not in str(result)


def test_content_fingerprint_changes_and_is_unambiguous():
    assert content_fingerprint("a", "bc") != content_fingerprint("ab", "c")
    assert content_fingerprint("a", "b") == content_fingerprint("a", "b")


def test_curated_synthetic_case_suite():
    path = Path(__file__).resolve().parents[2] / "data/evaluation/cases.json"
    cases = json.loads(path.read_text())["cases"]
    assert len(cases) >= 30
    for case in cases:
        actual = classify_project(
            case["description"], case["readme"], "https://example.test/synthetic-case"
        )
        for field, expected in case["expected"].items():
            assert actual[field] == expected, (
                case["id"],
                field,
                actual[field],
                expected,
            )


@pytest.mark.parametrize(
    "text",
    [
        "A security audit protocol for vibe-coded software.",
        "[The vibe-coded top 10](docs/top-10.md)",
        "Sets up rules so AI-written code stays correct.",
        "A guide to AI-assisted development.",
    ],
)
def test_third_party_development_descriptions_are_not_author_claims(text):
    result = classify_project("A development utility", text, "https://github.com/o/r")
    assert result["evidence_level"] != "explicit"


def test_chinese_vibe_coding_author_claim():
    result = classify_project(
        "一个音乐播放器", "本软件系 Vibe Coding 的产物。", "https://github.com/o/r"
    )
    assert result["evidence_level"] == "explicit"


def test_third_party_catalog_statements_do_not_verify_own_repository():
    for text in [
        "* [Awesome AI-Built Games](https://example.test) - Games built mostly with AI.",
        "The creator identifies this game as built with GPT in Codex.",
    ]:
        assert (
            classify_project("A curated list of games", text, "https://github.com/o/r")[
                "evidence_level"
            ]
            != "explicit"
        )


def test_application_description_wins_over_embedded_agent_skills():
    result = classify_project(
        "An intelligent clipboard productivity tool",
        "Includes agent skills for coding agents.",
        "https://github.com/o/r",
    )
    assert result["kind"] == "application"
