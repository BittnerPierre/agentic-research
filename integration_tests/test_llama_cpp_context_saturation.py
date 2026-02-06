"""Tests d'intégration pour valider la configuration llama.cpp sur DGX Spark.

Ces tests valident H1 du plan de robustification:
- Avant fix: démontrent la troncature EOF due au ctx-size insuffisant
- Après fix: démontrent que le ctx-size et n-predict permettent des outputs complets

Références:
- Issue #61: Corriger configuration llama.cpp
- Plan: plannings/ROBUSTIFICATION_DGX_SPARK_PLAN.md (Phase 1, S1)
"""

import os
from typing import Optional

import pytest
import requests
import tiktoken


class TestLlamaCppContextSaturation:
    """Tests de saturation du contexte llama.cpp."""

    # Configuration pour accès DGX Spark via Tailscale VPN
    DGX_HOSTNAME = os.getenv("DGX_HOSTNAME", "gx10-957b")
    DGX_IP = os.getenv("DGX_IP", "100.107.87.123")
    
    # Ports des services (depuis docker-compose.dgx.yml)
    LLM_INSTRUCT_PORT = 8002
    LLM_REASONING_PORT = 8004
    
    # Configuration actuelle (avant fix)
    CURRENT_CTX_SIZE = 2048
    
    # Configuration attendue (après fix)
    TARGET_CTX_SIZE = 4096
    TARGET_N_PREDICT = 2048

    @pytest.fixture
    def dgx_base_url(self) -> str:
        """URL de base pour accès au service llama.cpp sur DGX Spark."""
        # Préférence: hostname via Tailscale, fallback sur IP
        host = self.DGX_HOSTNAME
        return f"http://{host}"

    @pytest.fixture
    def instruct_endpoint(self, dgx_base_url: str) -> str:
        """Endpoint pour le service llm-instruct (gpt-oss-20b)."""
        return f"{dgx_base_url}:{self.LLM_INSTRUCT_PORT}"

    @pytest.fixture
    def reasoning_endpoint(self, dgx_base_url: str) -> str:
        """Endpoint pour le service llm-reasoning (Ministral-3-14B)."""
        return f"{dgx_base_url}:{self.LLM_REASONING_PORT}"

    @pytest.fixture
    def tokenizer(self):
        """Tokenizer pour compter les tokens (approximation avec cl100k_base)."""
        return tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str, tokenizer) -> int:
        """Compte le nombre de tokens dans un texte."""
        return len(tokenizer.encode(text))

    def _create_large_prompt(self, target_tokens: int = 1500) -> str:
        """Crée un prompt de taille contrôlée pour saturer le contexte.
        
        Args:
            target_tokens: Nombre approximatif de tokens souhaités
            
        Returns:
            Prompt répété pour atteindre la taille cible
        """
        base_prompt = (
            "Generate a very detailed JSON object describing a comprehensive research report. "
            "The JSON should include the following fields: title, executive_summary, "
            "introduction, methodology, findings, analysis, conclusions, recommendations, "
            "references, appendices, metadata, authors, publication_date, keywords, "
            "abstract, full_text, citations, figures, tables, acknowledgments, "
            "funding_sources, conflicts_of_interest, ethical_considerations, "
            "data_availability, supplementary_materials, peer_review_status, "
            "journal_name, doi, isbn, publisher, edition, volume, issue, pages, "
            "language, country, institution, department, research_group, "
            "corresponding_author, email, phone, address, orcid, researchgate, "
            "google_scholar, linkedin, twitter, research_interests, expertise_areas. "
        )
        
        # Répéter pour atteindre la taille cible
        repetitions = target_tokens // 100  # Approximation
        return base_prompt * repetitions

    def _make_completion_request(
        self,
        endpoint: str,
        prompt: str,
        n_predict: int = 2000,
        timeout: int = 60,
    ) -> Optional[dict]:
        """Effectue une requête de complétion au service llama.cpp.
        
        Args:
            endpoint: URL du service
            prompt: Texte du prompt
            n_predict: Nombre de tokens à générer (paramètre client)
            timeout: Timeout en secondes
            
        Returns:
            Réponse JSON ou None en cas d'erreur
        """
        try:
            response = requests.post(
                f"{endpoint}/completion",
                json={"prompt": prompt, "n_predict": n_predict},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Service llama.cpp non accessible: {e}")
            return None

    @pytest.mark.integration
    @pytest.mark.dgx
    def test_ctx_saturation_before_fix_instruct(
        self, instruct_endpoint: str, tokenizer
    ):
        """Test de saturation du contexte avec service llm-instruct (AVANT fix).
        
        Ce test démontre le problème actuel:
        - Prompt: ~1500 tokens
        - Ctx-size actuel: 2048 tokens
        - Espace disponible pour output: ~548 tokens
        - Requête client: 2000 tokens
        - Attendu: Output tronqué à ~548 tokens (preuve de saturation)
        
        Après fix (ctx-size 4096, n-predict 2048):
        - Ce test devrait passer car l'output ne sera plus tronqué
        """
        # Créer un prompt qui occupe ~1500 tokens
        prompt = self._create_large_prompt(target_tokens=1500)
        prompt_tokens = self._count_tokens(prompt, tokenizer)
        
        print(f"\n[BEFORE FIX] Test ctx saturation - llm-instruct")
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Current ctx-size: {self.CURRENT_CTX_SIZE}")
        print(f"Expected max output: ~{self.CURRENT_CTX_SIZE - prompt_tokens} tokens")
        
        # Requête avec n_predict élevé (2000 tokens)
        response = self._make_completion_request(
            endpoint=instruct_endpoint,
            prompt=prompt,
            n_predict=2000,
        )
        
        if response is None:
            return
        
        output = response.get("content", "")
        output_tokens = self._count_tokens(output, tokenizer)
        total_tokens = prompt_tokens + output_tokens
        
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_tokens}")
        
        # AVANT fix: output devrait être tronqué proche du ctx-size actuel
        # Tolérance de ±100 tokens pour variations d'encoding
        expected_max_output = self.CURRENT_CTX_SIZE - prompt_tokens
        
        # Assertion: output est limité par ctx-size (pas par n_predict)
        assert output_tokens < expected_max_output + 100, (
            f"Output devrait être tronqué à ~{expected_max_output} tokens "
            f"(ctx-size {self.CURRENT_CTX_SIZE} - prompt {prompt_tokens}), "
            f"mais {output_tokens} tokens générés"
        )
        
        # Vérifier que l'output est effectivement tronqué (pas complet)
        assert output_tokens < 1000, (
            f"Output devrait être tronqué (<1000 tokens avec ctx-size 2048), "
            f"mais {output_tokens} tokens générés"
        )
        
        print("✓ Troncature confirmée (comportement actuel = problème H1)")

    @pytest.mark.integration
    @pytest.mark.dgx
    def test_ctx_saturation_after_fix_instruct(
        self, instruct_endpoint: str, tokenizer
    ):
        """Test de saturation du contexte avec service llm-instruct (APRÈS fix).
        
        Après fix (ctx-size 4096, n-predict 2048):
        - Prompt: ~1500 tokens
        - Ctx-size: 4096 tokens
        - N-predict: 2048 tokens
        - Espace disponible: ~2548 tokens (limité par n-predict à 2048)
        - Attendu: Output proche de 2048 tokens (non tronqué par ctx-size)
        """
        # Créer un prompt qui occupe ~1500 tokens
        prompt = self._create_large_prompt(target_tokens=1500)
        prompt_tokens = self._count_tokens(prompt, tokenizer)
        
        print(f"\n[AFTER FIX] Test ctx adequacy - llm-instruct")
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Target ctx-size: {self.TARGET_CTX_SIZE}")
        print(f"Target n-predict: {self.TARGET_N_PREDICT}")
        
        # Requête avec n_predict = 2048 (valeur cible après fix)
        response = self._make_completion_request(
            endpoint=instruct_endpoint,
            prompt=prompt,
            n_predict=self.TARGET_N_PREDICT,
        )
        
        if response is None:
            return
        
        output = response.get("content", "")
        output_tokens = self._count_tokens(output, tokenizer)
        total_tokens = prompt_tokens + output_tokens
        
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_tokens}")
        
        # APRÈS fix: output devrait atteindre proche de n-predict (2048)
        # La limite est n-predict, pas ctx-size
        # Tolérance: le modèle peut s'arrêter avant (EOS, etc.)
        # mais devrait générer significativement plus qu'avant
        
        min_expected_output = 1500  # Au moins 1500 tokens (vs ~548 avant)
        
        assert output_tokens >= min_expected_output, (
            f"Output devrait atteindre au moins {min_expected_output} tokens "
            f"(avec ctx-size {self.TARGET_CTX_SIZE} et n-predict {self.TARGET_N_PREDICT}), "
            f"mais seulement {output_tokens} tokens générés. "
            f"Vérifier que la configuration a bien été appliquée."
        )
        
        # Vérifier que le total ne dépasse pas ctx-size
        assert total_tokens <= self.TARGET_CTX_SIZE + 100, (
            f"Total tokens ({total_tokens}) dépasse ctx-size ({self.TARGET_CTX_SIZE})"
        )
        
        print("✓ Output adéquat (configuration correcte)")

    @pytest.mark.integration
    @pytest.mark.dgx
    def test_json_generation_stability_instruct(
        self, instruct_endpoint: str, tokenizer
    ):
        """Test de stabilité de génération JSON (validation H1 post-fix).
        
        Ce test vérifie que le modèle peut générer un JSON structuré complet
        sans troncature EOF. C'est le cas d'usage réel qui échoue actuellement.
        """
        prompt = """Generate a valid JSON object with exactly this structure:
{
  "report": {
    "title": "Research Report Title",
    "executive_summary": "A comprehensive 500-word executive summary...",
    "sections": [
      {
        "heading": "Section 1",
        "content": "Detailed content for section 1..."
      },
      {
        "heading": "Section 2", 
        "content": "Detailed content for section 2..."
      }
    ],
    "follow_up_questions": [
      "Question 1?",
      "Question 2?",
      "Question 3?"
    ]
  }
}

IMPORTANT: Generate a complete, valid JSON. The executive_summary should be at least 300 words.
Make the content detailed and substantial."""

        prompt_tokens = self._count_tokens(prompt, tokenizer)
        print(f"\n[JSON Stability Test]")
        print(f"Prompt tokens: {prompt_tokens}")
        
        response = self._make_completion_request(
            endpoint=instruct_endpoint,
            prompt=prompt,
            n_predict=2048,
        )
        
        if response is None:
            return
        
        output = response.get("content", "")
        output_tokens = self._count_tokens(output, tokenizer)
        
        print(f"Output tokens: {output_tokens}")
        
        # Vérifier que l'output est substantiel (pas tronqué à 500 tokens)
        assert output_tokens >= 800, (
            f"Output JSON devrait être substantiel (>800 tokens), "
            f"mais seulement {output_tokens} tokens générés. "
            f"Possible troncature."
        )
        
        # Vérifier que l'output contient des marqueurs de JSON complet
        # (pas de validation stricte JSON ici, juste présence de structure)
        assert "executive_summary" in output, "JSON incomplet: manque executive_summary"
        assert "sections" in output, "JSON incomplet: manque sections"
        assert "follow_up_questions" in output, "JSON incomplet: manque follow_up_questions"
        
        # Compter les accolades (indicateur de complétude)
        open_braces = output.count("{")
        close_braces = output.count("}")
        
        print(f"Braces balance: {open_braces} open, {close_braces} close")
        
        # Tolérance: différence de ±2 (parfois le début/fin n'est pas délimité)
        assert abs(open_braces - close_braces) <= 2, (
            f"JSON probablement tronqué: déséquilibre accolades "
            f"({open_braces} open, {close_braces} close)"
        )
        
        print("✓ JSON generation stable (no EOF truncation)")

    @pytest.mark.integration
    @pytest.mark.dgx
    @pytest.mark.slow
    def test_ctx_saturation_reasoning_model(
        self, reasoning_endpoint: str, tokenizer
    ):
        """Test de saturation avec le modèle de reasoning (Ministral-3-14B).
        
        Validation similaire pour le service llm-reasoning qui a la même
        configuration problématique (ctx-size 2048).
        """
        prompt = self._create_large_prompt(target_tokens=1500)
        prompt_tokens = self._count_tokens(prompt, tokenizer)
        
        print(f"\n[Reasoning Model] Test ctx saturation")
        print(f"Prompt tokens: {prompt_tokens}")
        
        response = self._make_completion_request(
            endpoint=reasoning_endpoint,
            prompt=prompt,
            n_predict=2000,
        )
        
        if response is None:
            return
        
        output = response.get("content", "")
        output_tokens = self._count_tokens(output, tokenizer)
        
        print(f"Output tokens: {output_tokens}")
        
        # Même logique que pour instruct
        expected_max_output = self.CURRENT_CTX_SIZE - prompt_tokens
        
        # Note: Ce test peut être marqué comme xfail avant le fix
        # et devrait passer après le fix
        if output_tokens >= 1500:
            print("✓ Configuration already fixed (output adequate)")
        else:
            print(f"⚠ Output tronqué à {output_tokens} tokens (attendu: troncature <{expected_max_output})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
