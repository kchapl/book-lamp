import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("LLM_API_KEY")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")

        if self.api_key:
            # We use the OpenAI SDK which is compatible with many providers
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            logger.warning(
                "LLM_API_KEY is not set. AI recommendations will be unavailable. "
                "Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in your .env file to enable this feature."
            )
            self.client = None

    def generate_recommendations(
        self, liked_books: list[dict], existing_books: list[str]
    ) -> list[dict]:
        """Generate recommendations using an LLM via OpenAI SDK."""
        if not self.client:
            logger.warning("LLM_API_KEY is not set. Cannot generate recommendations.")
            return []

        system_prompt = (
            "You are a helpful and knowledgeable librarian recommending books to a reader. "
            "Use British English spelling (e.g., 'favourite', 'organised', 'colour') in the justification. "
            "IMPORTANT SAFETY GUIDELINES: Do not recommend any books that promote hate speech, illegal acts, self-harm, sexual violence, or extreme gore. "
            "If the user's reading history consists entirely of such topics, politely refuse to provide recommendations by returning an empty JSON array []. "
            "Output must be a JSON array of objects, containing exclusively the top 3 recommendations. "
            "Each object must have the following keys: 'title', 'author', 'isbn13', 'justification'. "
            "The 'justification' should be a 3-sentence explanation of why the user would like it based on their reading history."
        )

        # Build string representations of the lists
        liked_str = ", ".join(f"'{b['title']}' by {b['author']}" for b in liked_books)
        existing_str = ", ".join(f"'{title}'" for title in existing_books)

        user_prompt = f"The user recently highly rated: {liked_str}. "
        if existing_str:
            user_prompt += f"They have already read or plan to read: {existing_str}. "
        user_prompt += "Recommend 3 different books they should read next."

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.7,
            )

            content = chat_completion.choices[0].message.content
            # The model is asked to return a JSON object
            data = json.loads(content)

            # Extract the actual array from the data
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Look for the first list in the dict
                for val in data.values():
                    if isinstance(val, list):
                        return val

            return []
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}", exc_info=True)
            return []
