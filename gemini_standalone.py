from dotenv import load_dotenv
import os
import google.genai as genai
from google.genai import types

load_dotenv()
gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY')) 

prompt = input()
response = gemini.models.generate_content(
    model="gemini-2.5-flash", 
    contents=prompt,
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
    ),
)

print(response.candidates[0].content.parts[0].text)