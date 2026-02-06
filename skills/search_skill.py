import webbrowser
import logging
from core.skills import BaseSkill

class SearchSkill(BaseSkill):
    name = "Search"
    description = "Searches Google or opens websites."

    def handle(self, text: str) -> bool:
        lower = text.lower()
        if "search for" in lower or "google" in lower:
            query = lower.replace("search for", "").replace("google", "").strip()
            self.search(query)
            return True
        if lower.startswith("www.") or lower.endswith(".com"):
            url = lower if lower.startswith("http") else f"https://{lower}"
            self.open_url(url)
            return True
        return False

    def search(self, query):
        self.context.speak(f"Searching Google for {query}")
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)
        # Advanced scraping logic from the old websurf.py could be re-integrated here
        # but often just opening the browser is safer/better for general requests.

    def open_url(self, url):
        self.context.speak(f"Opening {url}")
        webbrowser.open(url)
