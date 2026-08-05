import os

def load_config():
    config = {
        'api_key': os.getenv('API_KEY', 'default_api_key'),
        'database_url': os.getenv('DATABASE_URL', 'sqlite:///default.db')
    }
    return config
