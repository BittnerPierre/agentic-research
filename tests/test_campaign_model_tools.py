"""Tests des outils modèles du skill benchmark-campaign (revue #210, finding 5).

Couvre : familles de modèles et détection famille-juge, filtre des configs de
campagne, génération de config (gabarits cloud/Spark, refus d'écrasement) et
contrôle du corpus gelé.
"""

import importlib.util
import sys
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "evaluations" / "campaign" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


list_models = _load("list_models")
new_model_config = _load("new_model_config")
verify_corpus = _load("verify_corpus")


class TestModelFamily:
    def test_strips_openai_prefix_and_date(self):
        assert list_models.model_family("openai/gpt-5.4-2026-03-05") == "gpt-5.4"

    def test_mini_is_a_distinct_family(self):
        assert list_models.model_family("openai/gpt-5.4-mini") != list_models.model_family(
            "gpt-5.4-2026-03-05"
        )

    def test_served_model_path_is_kept(self):
        assert (
            list_models.model_family("openai/deepseek-ai/DeepSeek-V4-Flash-0731")
            == "deepseek-ai/deepseek-v4-flash-0731"
        )


class TestJudgeFamilies:
    def test_reads_pinned_judges_from_answer_keys(self, tmp_path, monkeypatch):
        exercise = tmp_path / "exo-conceptuel"
        exercise.mkdir()
        (exercise / "answer_key.yaml").write_text("semantic_judge:\n  model: gpt-5.4-2026-03-05\n")
        monkeypatch.setattr(list_models, "EXERCISES", tmp_path)
        assert list_models.judge_families() == {"gpt-5.4": "exo-conceptuel"}

    def test_exercise_without_judge_is_ignored(self, tmp_path, monkeypatch):
        exercise = tmp_path / "exo-finance"
        exercise.mkdir()
        (exercise / "answer_key.yaml").write_text("items: []\n")
        monkeypatch.setattr(list_models, "EXERCISES", tmp_path)
        assert list_models.judge_families() == {}


class TestCampaignConfigFilter:
    CAMPAIGN: ClassVar[dict] = {
        "models": {"search_model": {"name": "openai/x"}},
        "manager": {"default_manager": "deep_manager"},
        "agents": {"writer_strategy": "decomposed"},
        "vector_search": {"provider": "chroma"},
    }

    def test_accepts_contract_config(self):
        assert list_models.is_campaign_config(self.CAMPAIGN)

    @pytest.mark.parametrize(
        "mutation",
        [
            {"manager": {"default_manager": "agentic_manager"}},
            {"agents": {"writer_strategy": "monolithic"}},
            {"vector_search": {"provider": "openai"}},
            {"models": {}},
        ],
    )
    def test_rejects_off_contract_configs(self, mutation):
        assert not list_models.is_campaign_config({**self.CAMPAIGN, **mutation})


class TestNewModelConfig:
    def _template(self, tmp_path: Path) -> Path:
        template = tmp_path / "template.yaml"
        template.write_text(
            yaml.safe_dump(
                {
                    "config_name": "gabarit",
                    "models": {
                        "search_model": {
                            "name": "openai/ancien",
                            "base_url": "http://spark1:8000/v1",
                            "api_key": "dummy",
                        },
                        "writer_model": "openai/ancien",
                    },
                }
            )
        )
        return template

    def test_spark_config_sets_endpoint_everywhere(self, tmp_path):
        target = new_model_config.create_config(
            "nouveau",
            "openai/org/Nouveau",
            base_url="http://spark1:8000/v1",
            template=self._template(tmp_path),
            configs_dir=tmp_path,
        )
        data = yaml.safe_load(target.read_text())
        assert data["config_name"] == "nouveau-decomposed"
        for spec in data["models"].values():
            assert spec["name"] == "openai/org/Nouveau"
            assert spec["base_url"] == "http://spark1:8000/v1"

    def test_cloud_config_drops_endpoint_and_key(self, tmp_path):
        target = new_model_config.create_config(
            "cloudy",
            "openai/gpt-x",
            template=self._template(tmp_path),
            configs_dir=tmp_path,
        )
        for spec in yaml.safe_load(target.read_text())["models"].values():
            assert "base_url" not in spec and "api_key" not in spec

    def test_never_overwrites_existing_config(self, tmp_path):
        (tmp_path / "config-pris-chroma-decomposed.yaml").write_text("config_name: pris\n")
        with pytest.raises(FileExistsError):
            new_model_config.create_config(
                "pris", "openai/x", template=self._template(tmp_path), configs_dir=tmp_path
            )


class TestVerifyCorpus:
    def _exercise(self, tmp_path: Path, sha: str) -> Path:
        exercise = tmp_path / "exo"
        (exercise / "corpus").mkdir(parents=True)
        (exercise / "source_manifest.yaml").write_text(
            yaml.safe_dump({"sources": [{"file_pattern": "Doc*.md", "sha256": sha}]})
        )
        return exercise

    def _sha(self, payload: bytes) -> str:
        import hashlib

        return hashlib.sha256(payload).hexdigest()

    def test_conforming_corpus_passes(self, tmp_path):
        exercise = self._exercise(tmp_path, self._sha(b"contenu gele"))
        (exercise / "corpus" / "Doc_1.md").write_bytes(b"contenu gele")
        assert verify_corpus.check_corpus(exercise, roots=[exercise / "corpus"]) == []

    def test_drifted_file_is_reported(self, tmp_path):
        exercise = self._exercise(tmp_path, self._sha(b"contenu gele"))
        (exercise / "corpus" / "Doc_1.md").write_bytes(b"contenu qui a derive")
        problems = verify_corpus.check_corpus(exercise, roots=[exercise / "corpus"])
        assert len(problems) == 1 and "sha256 attendu" in problems[0]

    def test_data_root_has_authority_over_corpus_copy(self, tmp_path):
        # Un data/ dérivé ne doit pas être blanchi par une copie conforme dans corpus/.
        exercise = self._exercise(tmp_path, self._sha(b"contenu gele"))
        (exercise / "corpus" / "Doc_1.md").write_bytes(b"contenu gele")
        data_root = tmp_path / "data"
        data_root.mkdir()
        (data_root / "Doc_1.md").write_bytes(b"drift dans data")
        problems = verify_corpus.check_corpus(exercise, roots=[data_root, exercise / "corpus"])
        assert len(problems) == 1

    def test_missing_file_is_reported(self, tmp_path):
        exercise = self._exercise(tmp_path, self._sha(b"contenu gele"))
        problems = verify_corpus.check_corpus(exercise, roots=[exercise / "corpus"])
        assert len(problems) == 1 and "aucun fichier trouvé" in problems[0]
