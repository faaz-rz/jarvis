import webbrowser
import logging
from urllib.parse import quote_plus
from core.skills import BaseSkill


class SearchSkill(BaseSkill):
    name = "Search"
    description = "Searches Google or opens websites."
    priority = 70

    def handle(self, text: str) -> bool:
        lower = text.lower()
        if "search for" in lower or "google" in lower:
            query = text
            for phrase in ("search for", "google"):
                index = query.lower().find(phrase)
                if index >= 0:
                    query = query[:index] + query[index + len(phrase):]
            query = query.strip()
            if not query:
                self.context.speak("Please tell me what you want to search for.")
                return True
            self.search(query)
            return True
        if lower.startswith(("http://", "https://", "www.")):
            url = text if lower.startswith("http") else f"https://{text}"
            self.open_url(url)
            return True
        return False

    def search(self, query):
        self.context.speak(f"Searching Google for {query}")
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)

    def open_url(self, url):
        self.context.speak(f"Opening {url}")
        webbrowser.open(url)
