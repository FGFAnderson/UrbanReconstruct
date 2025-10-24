from dotenv import load_dotenv
import os
import mapillary.interface as mly
import requests
import json

load_dotenv()

ACCESS_TOKEN = os.getenv('MAPILLARY_ACCESS_TOKEN')

mly.set_access_token(ACCESS_TOKEN)

