import requests
from bs4 import BeautifulSoup
import time
import re
from openai import OpenAI
import logging

# Configuration du logging pour le débogage
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

from openai import OpenAI

def query_llm_via_lmstudio(text):
    client = OpenAI(
        api_key="lm-studio",  # Clé ignorée par LM Studio
        base_url="http://localhost:1234/v1"
    )
    
    prompt = f"""
Lis attentivement cet article de presse économique et fais deux choses :

1. Résume le contenu en 4-5 phrases.
2. Donne une **analyse de tendance** sous forme de score :
   - +1 si l'article est légèrement haussier
   - +2 si clairement haussier
   - -1 si légèrement baissier
   - -2 si clairement baissier
   - 0 si neutre

Réponds dans ce format :
Résumé : ...
Tendance : ...
Texte :
{text}
"""
    try:
        response = client.chat.completions.create(
            model="mistral-7b-instruct-v0.2-GGUF",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Erreur LLM : {e}")
        return f"Erreur lors de l'analyse par le modèle : {str(e)}"




def extract_score_from_llm_output(output):
    match = re.search(r"Tendance\s*:\s*([+-]?\d+)", output)
    if not match:
        logging.warning("Format de tendance invalide, retour à 0.")
        return 0
    return int(match.group(1))

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

        print(f"📄 Contenu extrait :\n{full_text[:1000]}...")  # Affiche les 1000 premiers caractères
        llm_output = query_llm_via_lmstudio(full_text)
        trend_score = extract_score_from_llm_output(llm_output)

        print("\n📃 Réponse du LLM :")
        print(llm_output)
        print(f"📊 Trend Score (extrait) : {trend_score}")
        print("-" * 80)
        time.sleep(1)

if __name__ == "__main__":
    scrape_and_analyze(save_html=True)




