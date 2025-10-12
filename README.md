-----

# MarketTrend-LLM-Analyzer

-----

## 🚀 Overview

`MarketTrend-LLM-Analyzer` is a Python-based project designed to scrape financial news articles, extract their full content, and then leverage a local Large Language Model (LLM) via **LM Studio** for intelligent summarization and market trend analysis. This tool helps quickly get the gist of economic news and understand its potential impact on market sentiment (bullish, bearish, or neutral).

## ✨ Features

  * **Article Scraping**: Automatically fetches the latest financial articles from `boursedirect.fr`.
  * **Full Text Extraction**: intelligently extracts the complete article content, even with varied website structures.
  * **Local LLM Integration**: Communicates with a local LLM (e.g., Mistral-7B) running in LM Studio for offline processing.
  * **Summarization**: Generates concise summaries of lengthy articles.
  * **Trend Analysis**: Assigns a numerical score (+2 to -2) indicating the article's market trend sentiment (bullish, bearish, or neutral).
  * **Debugging Tools**: Includes options to save raw HTML for easier debugging of content extraction.

## 🛠️ Installation

### Prerequisites

Before you begin, ensure you have the following installed:

  * **Python 3.x**: This project is built with Python.
  * **LM Studio**: Download and install LM Studio from [https://lmstudio.ai/](https://lmstudio.ai/).
  * **LLM Model**: Within LM Studio, download a suitable model. This project is configured for `mistral-7b-instruct-v0.2-GGUF`, but you can use others as long as they run well in LM Studio.

### Project Setup

1.  **Clone the Repository** (once you create it on GitHub):

    ```bash
    git clone https://github.com/YourGitHubUser/MarketTrend-LLM-Analyzer.git
    cd MarketTrend-LLM-Analyzer
    ```

2.  **Create a Virtual Environment** (recommended):

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: `venv\Scripts\activate`
    ```

3.  **Install Dependencies**:

    ```bash
    pip install requests beautifulsoup4 openai pydantic
    ```

## ⚙️ Configuration

### LM Studio

Make sure your LM Studio server is running and accessible at `http://localhost:1234/v1`. The project's `query_llm_via_lmstudio` function is pre-configured for this endpoint.

## 🚀 Usage

To run the scraper and analysis, simply execute the main script:

```bash
python your_script_name.py # Replace your_script_name.py with the actual name of your Python file
```

The script will:

1.  Scrape the main news page of BourseDirect.
2.  For each article found, it will:
      * Attempt to fetch and parse its full content.
      * Send the content to your local LLM via LM Studio.
      * Print the LLM's summary and the extracted trend score.
3.  HTML files of scraped articles will be saved in the project directory for debugging (if `save_html=True` in `scrape_and_analyze` function call).

### Output Example

```
🔗 https://www.boursedirect.fr/fr/actualites/xxx
📌 Titre de l'article
📝 Résumé court (page d'accueil) : Ceci est un bref résumé de l'article.
📄 Contenu extrait :
Le contenu complet de l'article irait ici...
...
📃 Réponse du LLM :
Résumé : Cet article analyse... [4-5 phrases de résumé]
Tendance : +1
📊 Trend Score (extrait) : 1
--------------------------------------------------------------------------------
```

## 📄 License

This project is open-source and available under the MIT License.

-----
