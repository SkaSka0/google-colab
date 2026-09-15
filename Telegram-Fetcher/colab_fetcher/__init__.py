import os
import json
import logging

logging.basicConfig(level=logging.INFO)

CONFIG_PATH = "/content/Telegram_Fetcher/colab_fetcher/config/credentials.json"

ERROR_CREDENTIAL_NOT_FOUND = "Credential file not found at {}"
ERROR_INVALID_JSON = "Invalid JSON format in {}"

def load_credentials():
    if not os.path.exists(CONFIG_PATH):
        logging.error(ERROR_CREDENTIAL_NOT_FOUND.format(CONFIG_PATH))
        raise FileNotFoundError(ERROR_CREDENTIAL_NOT_FOUND.format(CONFIG_PATH))
    try:
        with open(CONFIG_PATH, "r") as file:
            logging.info(f"Loaded credentials from {CONFIG_PATH}")
            return json.load(file)
    except json.JSONDecodeError as e:
        logging.error(ERROR_INVALID_JSON.format(CONFIG_PATH) + f": {e}")
        raise ValueError(ERROR_INVALID_JSON.format(CONFIG_PATH))
