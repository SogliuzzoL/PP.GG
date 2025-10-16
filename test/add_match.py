import json

import requests
from dotenv import dotenv_values

config = dotenv_values(".env")
url = f"{config['backend_url']}/add_match"

with open("test/end_game.json") as f:
    match_data = json.load(f)

response = requests.post(url, json=match_data)
print(response.json())