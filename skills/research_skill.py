from core.skills import BaseSkill
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
import logging
import threading

class ResearchSkill(BaseSkill):
    name = "ResearchSkill"
    description = "Searches the web and learns from content."

    def __init__(self, context):
        super().__init__(context)

    def handle(self, text: str) -> bool:
        lower = text.lower()
        if type(text) != str: return False
        
        triggers = ["research", "learn about", "find out about", "search for"]
        for t in triggers:
            if text.lower().startswith(t):
                query = text[len(t):].strip()
                if query:
                    threading.Thread(target=self.perform_research, args=(query,)).start()
                    return True
        return False

    def perform_research(self, query):
        self.context.speak(f"Researching {query} on the web...")
        try:
            # 1. Search
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            
            if not results:
                self.context.speak(f"I couldn't find any information on {query}.")
                return

            # 2. Scrape & Aggregate
            aggregated_text = ""
            for r in results:
                url = r['href']
                try:
                    resp = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    # Get paragraphs
                    paragraphs = soup.find_all('p')
                    text_content = " ".join([p.get_text() for p in paragraphs[:5]]) # First 5 paragraphs per site
                    aggregated_text += f"\nSource: {r['title']}\n{text_content[:1000]}\n"
                except Exception:
                    continue
            
            if not aggregated_text:
                # Fallback to snippets
                aggregated_text = "\n".join([f"{r['title']}: {r['body']}" for r in results])

            # 3. Summarize with LLM
            prompt = f"The user asked to research '{query}'. Here is the raw data gathered from the web:\n{aggregated_text}\n\nProvide a comprehensive and concise summary of this information."
            summary = self.context.llm_query(prompt)
            
            self.context.speak(f"Here is what I found about {query}.")
            self.context.speak(summary)
            
            # 4. Save to Memory (Long-term)
            self.context.memory.set_preference(f"knowledge_{query.replace(' ', '_')}", summary)
            
        except Exception as e:
            logging.error(f"Research error: {e}")
            self.context.speak("I had trouble accessing the web properly.")
