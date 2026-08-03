import os
from .models import GeminiRemarkResult


def parse_with_gemini(remark):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Parse this logistics remark only. Do not infer missing financial data: " + str(remark),
            config={"response_mime_type": "application/json", "response_schema": GeminiRemarkResult},
        )
        return GeminiRemarkResult.model_validate_json(response.text)
    except Exception:
        return None

