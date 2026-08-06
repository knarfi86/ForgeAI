from forgeai.ai.ollama_manager import OllamaManager


class SomeOtherClass:
    def __init__(self):
        self.ollama_manager = OllamaManager()

    def check_ollama_availability(self):
        if self.ollama_manager.is_available():
            print("Ollama is available.")
        else:
            print("Ollama is not available.")

    def list_ollama_models(self):
        models = self.ollama_manager.get_models()
        if models:
            print("Available Ollama models:")
            for model in models:
                print(model)
        else:
            print("No Ollama models found.")
