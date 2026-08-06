import requests


class OllamaManager:
    def __init__(self, url="http://localhost:11434"):
        self.url = url

    def is_available(self):
        try:
            response = requests.get(self.url)
            return response.status_code == 200
        except Exception:
            return False

    def get_models(self):
        try:
            response = requests.get(f"{self.url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception:
            return []
