import requests
from bs4 import BeautifulSoup
import time
import re
import json
import logging
from typing import Literal
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "https://www.boursedirect.fr"

def extract_articles_from_main_page():
    url = f"{BASE_URL}/fr/actualites/categorie/analyse-de-la-tendance-des-marches"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Erreur lors de la requête sur {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = []
    items = soup.find_all("div", class_="timeline-item")

    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag:
            continue
        relative_url = link_tag["href"]
        full_url = BASE_URL + relative_url

        title_tag = item.find("h2", class_="timeline-title")
        summary_tag = item.find("p")

        title = title_tag.get_text(strip=True) if title_tag else "Sans titre"
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        articles.append({
            "url": full_url,
            "title": title,
            "summary": summary
        })

    return articles

def fetch_full_article_text(url, save_html=False):
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Erreur réseau pour {url}: {e}")
        return ""

    soup = BeautifulSoup(response.text, 'html.parser')

    # Sauvegarder le HTML brut pour inspection si demandé
    if save_html:
        with open(f"article_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        logging.info(f"HTML brut sauvegardé pour {url}")

    # Liste de sélecteurs à tester
    selectors = [
        ("div", {"class": ["article-content", "article", "main-article"]}),
        ("div", {"class": "content"}),
        ("article", {}),  # Balise <article> générique
        ("div", {"class": re.compile(".*article.*")}),  # Regex pour tout ce qui contient "article"
        ("div", {"id": re.compile(".*content.*")}),  # Regex pour tout ce qui contient "content"
    ]

    article_text = ""
    for tag, attrs in selectors:
        article_body = soup.find(tag, attrs)
        if article_body:
            article_text = article_body.get_text(separator="\n", strip=True)
            logging.info(f"Contenu extrait avec le sélecteur {tag}, {attrs}")
            break
        else:
            logging.warning(f"Sélecteur {tag}, {attrs} n'a rien trouvé.")

    if not article_text.strip():
        logging.error(f"Aucun contenu extrait pour {url}. Structure HTML inconnue.")
        # Afficher une partie du HTML pour débogage
        logging.debug(f"HTML brut (extrait) : {response.text[:500]}...")

    return article_text

class ArticleAnalysis(BaseModel):
    reasoning: str = Field(..., description="Justification factuelle en 2-3 phrases AVANT de scorer (chain-of-thought)")
    summary: str = Field(..., description="Résumé en 4-5 phrases")
    sentiment: int = Field(..., ge=-2, le=2, description="-2 clairement baissier à +2 clairement haussier (0 = neutre)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance dans le score, entre 0 et 1")
    horizon: Literal["court", "moyen", "long"] = Field(..., description="Horizon temporel de l'impact")
    sectors: list[str] = Field(default_factory=list, description="Secteurs ou actifs impactés")
    trigger_keywords: list[str] = Field(default_factory=list, description="Mots-clés déclencheurs du sentiment")


SYSTEM_PROMPT = """Tu es un analyste financier senior spécialisé dans l'analyse de sentiment de news boursières françaises et internationales.
Tu réponds UNIQUEMENT avec un objet JSON valide respectant strictement le schéma fourni — sans texte avant ni après, sans bloc markdown.
Tu raisonnes brièvement dans le champ 'reasoning' AVANT de produire le score, pour ancrer ta décision sur des faits de l'article."""


FEW_SHOT_EXAMPLES = [
    {
        "article": "Apple publie un chiffre d'affaires trimestriel record de 123 milliards de dollars, en hausse de 11% sur un an, porté par les ventes d'iPhone. Le titre gagne 5% en after-hours.",
        "output": {
            "reasoning": "CA record + croissance à deux chiffres + réaction immédiate très positive du marché (+5%). Signal clairement haussier, faits concordants.",
            "summary": "Apple annonce un trimestre record avec 123 Mds$ de chiffre d'affaires, en croissance de 11% en glissement annuel. La performance est principalement tirée par les ventes d'iPhone. Le marché réagit favorablement avec une hausse de 5% du titre en after-hours. Les indicateurs financiers dépassent les attentes du consensus.",
            "sentiment": 2,
            "confidence": 0.9,
            "horizon": "court",
            "sectors": ["technologie", "smartphones"],
            "trigger_keywords": ["chiffre d'affaires record", "hausse 11%", "+5% after-hours"]
        }
    },
    {
        "article": "La BCE relève ses taux directeurs de 50 points de base pour la sixième fois consécutive. Christine Lagarde évoque de futures hausses pour combattre l'inflation persistante.",
        "output": {
            "reasoning": "Resserrement monétaire prolongé + guidance hawkish explicite. Négatif pour actifs risqués et activité économique, mais largement anticipé donc impact modéré.",
            "summary": "La BCE poursuit son cycle de resserrement en relevant ses taux directeurs de 50 points de base pour la sixième fois consécutive. Christine Lagarde indique que d'autres hausses sont à prévoir afin de lutter contre une inflation jugée persistante. La posture reste résolument restrictive. La décision pèse sur les actifs risqués et la croissance à moyen terme.",
            "sentiment": -1,
            "confidence": 0.75,
            "horizon": "moyen",
            "sectors": ["banques", "immobilier", "actions européennes"],
            "trigger_keywords": ["hausse 50 pb", "inflation persistante", "futures hausses"]
        }
    }
]


def build_user_prompt(article_text: str) -> str:
    schema = json.dumps(ArticleAnalysis.model_json_schema(), ensure_ascii=False, indent=2)
    examples_block = "\n\n".join(
        f"### Exemple {i+1}\nArticle :\n{ex['article']}\n\nRéponse JSON :\n{json.dumps(ex['output'], ensure_ascii=False, indent=2)}"
        for i, ex in enumerate(FEW_SHOT_EXAMPLES)
    )
    return f"""Analyse l'article ci-dessous et retourne un JSON conforme à ce schéma :

{schema}

{examples_block}

### Article à analyser
{article_text}

### Réponse JSON
"""


def query_llm_via_lmstudio(text: str) -> "ArticleAnalysis | None":
    client = OpenAI(api_key="lm-studio", base_url="http://localhost:1234/v1")
    try:
        response = client.chat.completions.create(
            model="mistral-7b-instruct-v0.2-GGUF",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(text)},
            ],
            temperature=0.1,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
    except Exception as e:
        logging.error(f"Erreur LLM : {e}")
        return None

    return parse_analysis(raw)


def parse_analysis(raw: str) -> "ArticleAnalysis | None":
    payload = raw.strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```(?:json)?\s*|\s*```$", "", payload, flags=re.MULTILINE).strip()
    if not payload.startswith("{"):
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if not match:
            logging.error(f"Pas de JSON détecté dans la réponse LLM : {raw[:200]}")
            return None
        payload = match.group(0)

    try:
        return ArticleAnalysis.model_validate_json(payload)
    except ValidationError as e:
        logging.error(f"Validation Pydantic échouée : {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSON invalide : {e} | payload: {payload[:200]}")
        return None

def scrape_and_analyze(save_html=True):
    articles = extract_articles_from_main_page()
    if not articles:
        logging.error("Aucun article trouvé sur la page principale.")
        return

    for article in articles:
        print(f"🔗 {article['url']}")
        print(f"📌 {article['title']}")
        print(f"📝 Résumé court (page d'accueil) : {article['summary']}")

        full_text = fetch_full_article_text(article['url'], save_html=save_html)
        if not full_text.strip():
            print("⚠️ Article vide ou structure inconnue.")
            print(f"📄 Contenu brut non disponible, vérifiez le fichier HTML sauvegardé ou le log.")
            continue

        print(f"📄 Contenu extrait :\n{full_text[:1000]}...")
        analysis = query_llm_via_lmstudio(full_text)

        if analysis is None:
            print("❌ Analyse LLM indisponible (voir logs).")
            print("-" * 80)
            continue

        print("\n📃 Analyse :")
        print(f"  💭 Raisonnement : {analysis.reasoning}")
        print(f"  📝 Résumé       : {analysis.summary}")
        print(f"  📊 Sentiment    : {analysis.sentiment:+d}")
        print(f"  🎯 Confiance    : {analysis.confidence:.0%}")
        print(f"  ⏳ Horizon      : {analysis.horizon} terme")
        print(f"  🏭 Secteurs     : {', '.join(analysis.sectors) or '—'}")
        print(f"  🔑 Mots-clés    : {', '.join(analysis.trigger_keywords) or '—'}")
        print("-" * 80)
        time.sleep(1)

if __name__ == "__main__":
    scrape_and_analyze(save_html=True)




