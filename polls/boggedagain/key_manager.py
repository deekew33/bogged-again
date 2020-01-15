import os
from typing import List


def get_google_certs() -> List[str]:
    """Return list containing search engine ID and API key from google_api_certs.env"""

    # Get absolute path to key_manager.py (google_api_certs.env is in same directory)
    script_dir = os.path.dirname(__file__)

    # Name and absolute path to file containing ID/key
    certs_filename = "google_api_certs.env"
    certs_filepath = os.path.join(script_dir, certs_filename)

    # Read search engine ID (1st line) and API key (2nd line) from file
    with open(certs_filepath, 'r') as f:
        certs = f.readlines()

    if len(certs) != 2:
        raise RuntimeError("google_api_certs.env must contain search engine ID (1st line) and API key (2nd line)")

    # Remove trailing newline character from each line and return
    return [line.rstrip() for line in certs]


def get_google_cse_id() -> str:
    """Return string containing custom search engine ID from google_api_certs.env"""

    try:
        return get_google_certs()[0]
    except RuntimeError:
        print("Error: Unable to retrieve custom search engine ID from google_api_certs.env")
        raise


def get_google_api_key() -> str:
    """Return string containing API key from google_api_certs.env"""

    try:
        return get_google_certs()[1]
    except RuntimeError:
        print("Error: Unable to retrieve API key from google_api_certs.env")
        raise
