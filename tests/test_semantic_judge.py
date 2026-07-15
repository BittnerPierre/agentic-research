from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from evaluations.semantic_judge import (
    AdversaryVerdict,
    ConceptualAdjudication,
    OpenAIJudgeClient,
    PrimaryVerdict,
    StructuredCall,
    adjudicate_conceptual_run,
    adjudicate_semantic_run,
    apply_conceptual_adjudication,
    apply_finance_adequacy_veto,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class _FakeJudge:
    def __init__(self, outputs: list[BaseModel | None]):
        self.outputs = list(outputs)
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    async def call(self, *, instructions: str, input_text: str, output_type):
        self.calls.append((instructions, input_text, output_type))
        output = self.outputs.pop(0)
        return StructuredCall(
            parsed=output,
            attempts=[{"attempt": 1, "response": {"fixture": True}}],
            error=None if output is not None else "fixture returned no output",
        )


class _FakeResponsesAPI:
    def __init__(self, parsed: BaseModel):
        self.parsed = parsed
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        parsed = self.parsed

        class _Response:
            output_parsed = parsed

            @staticmethod
            def model_dump(mode="json"):
                return {"id": "response-fixture", "mode": mode}

        return _Response()


class _FakeOpenAI:
    def __init__(self, parsed: BaseModel):
        self.responses = _FakeResponsesAPI(parsed)


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, str, list[dict]]:
    exercise = tmp_path / "exercise"
    corpus = exercise / "corpus"
    corpus.mkdir(parents=True)
    request = "Explain agent tools from the supplied source."
    (exercise / "syllabus.md").write_text(request, encoding="utf-8")
    (exercise / "spec.yaml").write_text("required_chapters: []\n", encoding="utf-8")
    raw = "# Agents\n\nA tool has a declared name and parameter schema.\n"
    (corpus / "Agents_1.md").write_text(raw, encoding="utf-8")
    (exercise / "source_manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "url": "https://example.test/agents",
                        "file_pattern": "Agents*.md",
                        "sha256": _sha256(raw),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (exercise / "answer_key.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "conceptual",
                "contract_version": 2,
                "request_file": "syllabus.md",
                "require_citation": True,
                "semantic_judge": {
                    "model": "gpt-5.4-2026-03-05",
                    "reasoning_effort": "high",
                    "protocol": "judge_then_contradictor",
                    "authority": "semantic_authority",
                    "requirement_sections": ["must_cover"],
                    "accepted_languages": ["English", "French"],
                },
                "must_cover": [
                    {
                        "id": "function_calling",
                        "concept": "function calling",
                        "expected_answer": "Tools have declared names and parameter schemas.",
                        "required_points": ["A declared tool", "Arguments or parameters"],
                        "critical_errors": ["Claims arguments are always correct"],
                        "source_files": ["Agents"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    run = tmp_path / "benchmarks" / "runs" / "run"
    run.mkdir(parents=True)
    raw_archive = run / "raw_sources"
    raw_archive.mkdir()
    (raw_archive / "Agents_1.md").write_text(raw, encoding="utf-8")
    chunk_text = "A tool has a declared name and parameter schema."
    chunk_id = "abcdef12-3456:0"
    (run / "chunks.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "chunks": [
                    {
                        "chunk_id": chunk_id,
                        "document_id": "abcdef12-3456",
                        "chunk_index": 0,
                        "filename": "Agents_1.md",
                        "source": "https://example.test/agents",
                        "text": chunk_text,
                        "sha256": _sha256(chunk_text),
                        "resolved": True,
                    }
                ],
                "conflicts": [],
            }
        ),
        encoding="utf-8",
    )
    report = "Function calling declares tools and parameter schemas before use [S1]."
    sources = [{"source_id": "S1", "content": "generated summary", "doc_ids": [chunk_id]}]
    (run / "report.md").write_text(report, encoding="utf-8")
    (run / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    wrapped_request = f"<research_request>\n{request}\n</research_request>"
    (run / "stats.json").write_text(
        json.dumps({"query": wrapped_request, "models": {"writer": "openai/mistral-small"}}),
        encoding="utf-8",
    )
    return exercise, run, wrapped_request, report, sources


def _pass(report: str) -> PrimaryVerdict:
    return PrimaryVerdict(
        requirement_id="function_calling",
        verdict="pass",
        report_quote=report,
        cited_source_ids=["S1"],
        supporting_chunk_ids=["abcdef12-3456:0"],
        error_type="none",
        reasoning="The explanation matches the closed rubric and the cited raw chunk.",
        confidence="high",
    )


def _uphold() -> AdversaryVerdict:
    return AdversaryVerdict(
        requirement_id="function_calling",
        verdict="uphold_pass",
        reasoning="No omission, contradiction, or citation mismatch survives review.",
        confidence="high",
    )


@pytest.mark.asyncio
async def test_openai_judge_uses_pinned_snapshot_without_incompatible_sampling_params() -> None:
    parsed = _pass("Function calling is grounded [S1].")
    fake_openai = _FakeOpenAI(parsed)
    client = OpenAIJudgeClient(
        model="gpt-5.4-2026-03-05",
        reasoning_effort="high",
        client=fake_openai,
    )

    result = await client.call(
        instructions="closed rubric",
        input_text="evidence pack",
        output_type=PrimaryVerdict,
    )

    assert result.parsed == parsed
    assert fake_openai.responses.calls == [
        {
            "instructions": "closed rubric",
            "input": "evidence pack",
            "text_format": PrimaryVerdict,
            "model": "gpt-5.4-2026-03-05",
            "reasoning": {"effort": "high"},
            "max_output_tokens": 4000,
            "store": False,
        }
    ]
    assert "temperature" not in fake_openai.responses.calls[0]
    assert "top_p" not in fake_openai.responses.calls[0]


@pytest.mark.asyncio
async def test_conceptual_judge_requires_primary_and_adversary_agreement(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    client = _FakeJudge([_pass(report), _uphold()])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "complete"
    assert result.qualified is True
    assert result.counts == {"pass": 1, "fail": 0, "indeterminate": 0, "needs_review": 0}
    assert [call[2] for call in client.calls] == [PrimaryVerdict, AdversaryVerdict]
    assert result.judge["model"] == "gpt-5.4-2026-03-05"
    assert result.judge["confidence_used_for_decision"] is False
    assert json.loads(client.calls[0][1])["authority_policy"] == "semantic_authority"


@pytest.mark.asyncio
async def test_finance_adequacy_uses_generic_engine_and_json_corpus_manifest(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    answer_key_path = exercise / "answer_key.yaml"
    answer_key = yaml.safe_load(answer_key_path.read_text(encoding="utf-8"))
    answer_key["mode"] = "numeric"
    answer_key["semantic_judge"]["authority"] = "adequacy_veto"
    answer_key["semantic_judge"]["requirement_sections"] = ["adequacy_requirements"]
    answer_key["adequacy_requirements"] = answer_key.pop("must_cover")
    answer_key_path.write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    raw_path = exercise / "corpus" / "Agents_1.md"
    (exercise / "source_manifest.yaml").unlink()
    (exercise / "corpus" / "manifest.json").write_text(
        json.dumps({"generated_files": {raw_path.name: _sha256(raw_path.read_text())}}),
        encoding="utf-8",
    )
    client = _FakeJudge([_pass(report), _uphold()])

    result = await adjudicate_semantic_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "complete"
    assert result.qualified is True
    assert result.judge["authority"] == "adequacy_veto"
    assert json.loads(client.calls[0][1])["authority_policy"] == "adequacy_veto"


@pytest.mark.asyncio
async def test_conceptual_judge_does_not_run_adversary_after_primary_fail(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    primary_fail = PrimaryVerdict(
        requirement_id="function_calling",
        verdict="fail",
        report_quote=report,
        error_type="incorrect",
        reasoning="The report does not satisfy the declared expected answer.",
        confidence="high",
    )
    client = _FakeJudge([primary_fail])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "complete"
    assert result.requirements[0].final_status == "fail"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_conceptual_judge_accepts_source_subreference_citation_form(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    report = report.replace("[S1]", "[S1:2]")
    (run / "report.md").write_text(report, encoding="utf-8")

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=_FakeJudge([_pass(report), _uphold()]),
    )

    assert result.qualified is True


@pytest.mark.asyncio
async def test_conceptual_judge_protocol_is_invariant_to_unrequested_layout(
    tmp_path: Path,
) -> None:
    results = []
    reports = [
        "### API tools\n\nFunction calling declares tools and parameter schemas before use [S1].",
        "- Function calling declares tools and parameter schemas before use [S1].",
    ]
    for index, report in enumerate(reports):
        exercise, run, request, _original, sources = _fixture(tmp_path / str(index))
        (run / "report.md").write_text(report, encoding="utf-8")
        result = await adjudicate_conceptual_run(
            run_dir=run,
            exercise=exercise,
            report=report,
            sources=sources,
            request=request,
            client=_FakeJudge([_pass(report), _uphold()]),
        )
        results.append(result)

    assert [result.counts for result in results] == [
        {"pass": 1, "fail": 0, "indeterminate": 0, "needs_review": 0},
        {"pass": 1, "fail": 0, "indeterminate": 0, "needs_review": 0},
    ]
    assert all(result.qualified for result in results)


@pytest.mark.asyncio
async def test_conceptual_judge_protocol_preserves_french_report_evidence(
    tmp_path: Path,
) -> None:
    exercise, run, request, _original, sources = _fixture(tmp_path)
    report = (
        "L'appel de fonction déclare les outils et le schéma de leurs paramètres avant "
        "leur utilisation [S1]."
    )
    (run / "report.md").write_text(report, encoding="utf-8")

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=_FakeJudge([_pass(report), _uphold()]),
    )

    assert result.qualified is True
    assert result.requirements[0].primary is not None
    assert result.requirements[0].primary.report_quote == report


@pytest.mark.asyncio
async def test_conceptual_judge_disagreement_fails_closed(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    refute = AdversaryVerdict(
        requirement_id="function_calling",
        verdict="refute_pass",
        report_quote=report,
        counterevidence_chunk_ids=["abcdef12-3456:0"],
        reasoning="The cited passage does not establish execution of the proposed arguments.",
        confidence="medium",
    )

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=_FakeJudge([_pass(report), refute]),
    )

    assert result.qualified is False
    assert result.requirements[0].final_status == "needs_review"
    assert result.blockers == ["function_calling: needs_review"]


@pytest.mark.asyncio
async def test_conceptual_judge_rejects_non_verbatim_evidence_quote(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    invalid_pass = _pass("A paraphrase that is not present in the report [S1].")
    client = _FakeJudge([invalid_pass])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.requirements[0].final_status == "indeterminate"
    assert result.status == "evaluation_failed"
    assert result.requirements[0].protocol_errors == ["report quote is not an exact substring"]
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_conceptual_judge_rejects_summary_without_resolved_doc_id(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    sources[0]["doc_ids"] = []
    (run / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    client = _FakeJudge([_pass(report)])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.requirements[0].final_status == "indeterminate"
    assert "cited source has no resolved raw chunks" in result.requirements[0].protocol_errors


@pytest.mark.asyncio
async def test_semantic_judge_requires_portable_raw_source_archive(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    (run / "raw_sources" / "Agents_1.md").unlink()
    client = _FakeJudge([])

    result = await adjudicate_semantic_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "evaluation_failed"
    assert result.blockers == ["portable raw source archive is incomplete"]
    assert client.calls == []


@pytest.mark.asyncio
async def test_conceptual_judge_invalid_structured_output_fails_closed(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=_FakeJudge([None]),
    )

    assert result.status == "evaluation_failed"
    assert result.qualified is False
    assert result.requirements[0].final_status == "indeterminate"
    assert result.blockers[0] == "judge protocol validation failed"


@pytest.mark.asyncio
async def test_conceptual_judge_rejects_report_different_from_portable_pack(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    client = _FakeJudge([])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report + "\nInjected after the run.",
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "contract_mismatch"
    assert "portable report is unavailable or differs" in result.contract["errors"][0]
    assert client.calls == []


@pytest.mark.asyncio
async def test_conceptual_judge_stops_before_model_call_on_prompt_drift(tmp_path: Path) -> None:
    exercise, run, _request, report, sources = _fixture(tmp_path)
    client = _FakeJudge([])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request="A different report request.",
        client=client,
    )

    assert result.status == "contract_mismatch"
    assert result.qualified is False
    assert client.calls == []


@pytest.mark.asyncio
async def test_conceptual_judge_cannot_be_the_candidate_model(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    (run / "stats.json").write_text(
        json.dumps(
            {
                "query": request,
                "models": {"writer": "openai/gpt-5.4@https://api.openai.com/v1"},
            }
        ),
        encoding="utf-8",
    )
    client = _FakeJudge([])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "evaluation_failed"
    assert result.blockers == ["semantic judge is also a candidate model"]
    assert client.calls == []


@pytest.mark.asyncio
async def test_conceptual_judge_rejects_adequacy_veto_authority_before_model_call(
    tmp_path: Path,
) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    answer_key_path = exercise / "answer_key.yaml"
    answer_key = yaml.safe_load(answer_key_path.read_text(encoding="utf-8"))
    answer_key["semantic_judge"]["authority"] = "adequacy_veto"
    answer_key_path.write_text(yaml.safe_dump(answer_key), encoding="utf-8")
    client = _FakeJudge([])

    result = await adjudicate_conceptual_run(
        run_dir=run,
        exercise=exercise,
        report=report,
        sources=sources,
        request=request,
        client=client,
    )

    assert result.status == "evaluation_failed"
    assert result.blockers == ["semantic judge authority is incompatible with exercise mode"]
    assert client.calls == []


def test_apply_conceptual_judgment_replaces_lexical_authority(tmp_path: Path) -> None:
    exercise, run, request, report, sources = _fixture(tmp_path)
    adjudication = asyncio.run(
        adjudicate_conceptual_run(
            run_dir=run,
            exercise=exercise,
            report=report,
            sources=sources,
            request=request,
            client=_FakeJudge([_pass(report), _uphold()]),
        )
    )
    lexical = {
        "score": 0.0,
        "qualified": False,
        "requirements": [{"id": "function_calling", "status": "missing_or_unsupported"}],
        "coverage": {"hit": 0, "total": 1, "pct": 0.0},
        "qualification": {
            "passed": False,
            "blockers": ["critical requirements failed", "conceptual judge not run"],
            "critical_requirement_failures": ["function calling"],
            "format_blockers": [],
        },
        "root_cause": {"verdict": "writer/agenda"},
    }

    merged = apply_conceptual_adjudication(lexical, adjudication)

    assert merged["score"] == 100.0
    assert merged["qualified"] is True
    assert merged["requirements"][0]["status"] == "pass"
    assert merged["lexical_diagnostic"]["score"] == 0.0


def test_finance_adequacy_pass_cannot_rehabilitate_deterministic_failure() -> None:
    deterministic = {
        "score": 60.0,
        "score_authority": "deterministic_numeric",
        "qualified": False,
        "accuracy": {"matching": 41, "wrong": 1},
        "fabrication": {"count": 0, "items": []},
        "qualification": {
            "passed": False,
            "blockers": ["wrong factual claims", "finance adequacy judge not run"],
        },
        "root_cause": {"verdict": "writer/accuracy"},
    }
    adjudication = ConceptualAdjudication(
        status="complete",
        qualified=True,
        counts={"pass": 6, "fail": 0, "indeterminate": 0, "needs_review": 0},
    )

    merged = apply_finance_adequacy_veto(deterministic, adjudication)

    assert merged["qualified"] is False
    assert merged["qualification"]["blockers"] == ["wrong factual claims"]
    assert merged["score"] == deterministic["score"]
    assert merged["score_authority"] == "deterministic_numeric"
    assert merged["accuracy"] == deterministic["accuracy"]
    assert merged["fabrication"] == deterministic["fabrication"]
    assert merged["root_cause"]["verdict"] == "writer/accuracy"


def test_finance_adequacy_veto_blocks_clean_deterministic_grade() -> None:
    deterministic = {
        "score": 100.0,
        "score_authority": "deterministic_numeric",
        "qualified": False,
        "qualification": {
            "passed": False,
            "blockers": ["finance adequacy judge not run"],
        },
        "root_cause": {"verdict": "ok"},
    }
    adjudication = ConceptualAdjudication(
        status="complete",
        qualified=False,
        blockers=["comparison_adequacy: fail"],
        counts={"pass": 5, "fail": 1, "indeterminate": 0, "needs_review": 0},
    )

    merged = apply_finance_adequacy_veto(deterministic, adjudication)

    assert merged["qualified"] is False
    assert merged["qualification"]["blockers"] == ["comparison_adequacy: fail"]
    assert merged["score"] == 100.0
    assert merged["root_cause"]["finance_adequacy"] == "veto"


def test_fixed_conceptual_contract_has_closed_rubric_and_pinned_judge() -> None:
    exercise = Path(__file__).parents[1] / "evaluations" / "exercises" / "ai-engineering-syllabus"
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    requirements = [
        *answer_key["must_cover"],
        *answer_key["report_requirements"],
    ]

    assert answer_key["contract_version"] == 2
    assert answer_key["semantic_judge"] == {
        "model": "gpt-5.4-2026-03-05",
        "reasoning_effort": "high",
        "protocol": "judge_then_contradictor",
        "authority": "semantic_authority",
        "requirement_sections": ["must_cover", "report_requirements"],
        "accepted_languages": ["English", "French"],
    }
    assert len(requirements) == 16
    assert len({requirement["id"] for requirement in requirements}) == 16
    assert all(
        requirement.get(field)
        for requirement in requirements
        for field in ("expected_answer", "required_points", "critical_errors")
    )
    request_path = (exercise / answer_key["request_file"]).resolve()
    assert request_path == Path(__file__).parents[1] / "test_files" / "syllabus.md"
    assert request_path.is_file()


def test_fixed_finance_contract_declares_adequacy_veto_without_numeric_authority() -> None:
    exercise = Path(__file__).parents[1] / "evaluations" / "exercises" / "ai-capex-intensity"
    answer_key = yaml.safe_load((exercise / "answer_key.yaml").read_text(encoding="utf-8"))
    requirements = answer_key["adequacy_requirements"]

    assert answer_key["semantic_judge"]["authority"] == "adequacy_veto"
    assert answer_key["semantic_judge"]["requirement_sections"] == ["adequacy_requirements"]
    assert answer_key["semantic_judge"]["model"] == "gpt-5.4-2026-03-05"
    assert len(requirements) == 6
    assert len({requirement["id"] for requirement in requirements}) == 6
    assert all(
        requirement.get(field)
        for requirement in requirements
        for field in ("expected_answer", "required_points", "critical_errors")
    )
