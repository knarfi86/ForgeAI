import sys

from config import load_config
from utils import initialize_logging

def main():
    config = load_config()
    initialize_logging(config)
    
    print("ForgeAI gestartet")

if __name__ == '__main__':
    main()
