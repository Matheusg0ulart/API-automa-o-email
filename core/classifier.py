import re
import unicodedata
from typing import Dict, List, Tuple, Any


def normalize_text(text: str) -> str:
    """Converte o texto para minúsculas e remove acentos para garantir matching infalível."""
    if not text:
        return ""
    text = text.lower()
    # Decomposição NFD separa letras de seus acentos
    normalized = unicodedata.normalize("NFD", text)
    # Remove marcas diacríticas (acentos)
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_accents


class EmailClassifier:
    """Classificador inteligente de e-mails baseado em regras ponderadas e heurísticas."""

    def __init__(self, rules_config: Dict[str, Any], company_domain: str = ""):
        self.categories = rules_config.get("categories", [])
        self.weights = rules_config.get("weights", {
            "subject_match": 3.0,
            "body_match": 1.0,
            "sender_domain_match": 10.0,
            "sender_email_match": 20.0
        })
        self.threshold = float(rules_config.get("score_threshold", 2.0))
        self.default_folder = rules_config.get("default_folder", "Outros")
        self.company_domain = company_domain.strip().lower()

    def classify(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa o e-mail e retorna a categoria correspondente com pontuação e justificativa.
        """
        raw_subject = email_data.get("subject", "")
        raw_body = email_data.get("body", "")
        sender_email = email_data.get("sender_email", "").lower()
        sender_domain = email_data.get("sender_domain", "").lower()

        norm_subject = normalize_text(raw_subject)
        # Limita análise do corpo para primeiros 10.000 caracteres para alta performance
        norm_body = normalize_text(raw_body[:10000])

        category_scores: Dict[str, float] = {}
        category_reasons: Dict[str, List[str]] = {}

        w_subject = self.weights.get("subject_match", 3.0)
        w_body = self.weights.get("body_match", 1.0)
        w_domain = self.weights.get("sender_domain_match", 10.0)
        w_email = self.weights.get("sender_email_match", 20.0)

        for cat in self.categories:
            cat_id = cat["id"]
            score = 0.0
            reasons = []

            # 1. Verificação de remetentes específicos cadastrados na regra
            rule_senders = [s.lower() for s in cat.get("senders", [])]
            if sender_email and sender_email in rule_senders:
                score += w_email
                reasons.append(f"Remetente cadastrado ({sender_email})")
            elif sender_domain and sender_domain in rule_senders:
                score += w_domain
                reasons.append(f"Domínio cadastrado (@{sender_domain})")

            # 2. Regra especial para Empresa Interno: domínio da própria empresa
            if cat_id == "empresa" and self.company_domain:
                if sender_domain == self.company_domain:
                    score += w_domain
                    reasons.append(f"Domínio da empresa (@{self.company_domain})")

            # 3. Matching de palavras-chave no Assunto
            subject_keywords = cat.get("keywords_subject", [])
            for kw in subject_keywords:
                norm_kw = normalize_text(kw)
                if not norm_kw:
                    continue
                # Busca com limite de palavra quando termo for curto, ou busca direta
                pattern = r"(?:\b|\W|^)" + re.escape(norm_kw) + r"(?:\b|\W|$)"
                if re.search(pattern, norm_subject):
                    score += w_subject
                    reasons.append(f"Assunto: '{kw}'")

            # 4. Matching de palavras-chave no Corpo
            body_keywords = cat.get("keywords_body", [])
            for kw in body_keywords:
                norm_kw = normalize_text(kw)
                if not norm_kw:
                    continue
                pattern = r"(?:\b|\W|^)" + re.escape(norm_kw) + r"(?:\b|\W|$)"
                if re.search(pattern, norm_body):
                    score += w_body
                    reasons.append(f"Corpo: '{kw}'")

            category_scores[cat_id] = score
            category_reasons[cat_id] = reasons

        # Determina a categoria vencedora
        best_cat_id = None
        best_score = 0.0

        for cat_id, score in category_scores.items():
            if score > best_score:
                best_score = score
                best_cat_id = cat_id

        # Se ultrapassou o limiar mínimo de confiança
        if best_cat_id and best_score >= self.threshold:
            matching_cat = next((c for c in self.categories if c["id"] == best_cat_id), None)
            category_name = matching_cat["name"] if matching_cat else best_cat_id
            target_folder = matching_cat["folder"] if matching_cat else best_cat_id.capitalize()
            reasons = category_reasons.get(best_cat_id, [])
        else:
            best_cat_id = "outros"
            category_name = "Outros / Geral"
            target_folder = self.default_folder
            reasons = ["Não atingiu pontuação mínima de filtro"]

        return {
            "category_id": best_cat_id,
            "category_name": category_name,
            "target_folder": target_folder,
            "score": round(best_score, 2),
            "reasons": reasons[:4],  # Principais 4 motivos
            "all_scores": category_scores
        }
