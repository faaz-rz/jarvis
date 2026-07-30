import webbrowser
import logging
from urllib.parse import quote_plus
from core.skills import BaseSkill
from core.tools import RiskLevel, ToolSpec


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
            self.context.speak(self.search(query))
            return True
        if lower.startswith(("http://", "https://", "www.")):
            url = text if lower.startswith("http") else f"https://{text}"
            self.context.speak(self.open_url(url))
            return True
        return False

    def tools(self):
        return [
            ToolSpec(
                name="web_search",
                description="Open a browser search for the user's query.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "maxLength": 500,
                            "description": "The exact search query.",
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                handler=self.search,
                risk=RiskLevel.ACTION,
            ),
            ToolSpec(
                name="open_website",
                description="Open an HTTP or HTTPS website in the default browser.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "maxLength": 1000,
                            "description": "A complete HTTP or HTTPS URL.",
                        }
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
                handler=self.open_url,
                risk=RiskLevel.ACTION,
            ),
        ]

    def search(self, query):
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        opened = webbrowser.open(url)
        return (
            f"Opened a browser search for: {query}"
            if opened
            else f"Requested a browser search for: {query}"
        )

    def open_url(self, url):
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Only HTTP and HTTPS URLs are allowed.")
        opened = webbrowser.open(url)
        return f"Opened {url}." if opened else f"Requested opening {url}."
