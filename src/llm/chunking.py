import tiktoken
import logging
from bs4 import BeautifulSoup
from typing import List

logger = logging.getLogger(__name__)

class ContentChunker:
    """Intelligently chunks HTML/Text to prevent 413 Payload Too Large errors."""
    
    def __init__(self, model: str = "gpt-3.5-turbo", max_tokens: int = 4000):
        # We use a standard encoding for chunk sizing regardless of underlying model
        self.encoding = tiktoken.encoding_for_model(model)
        self.max_tokens = max_tokens

    def clean_html(self, html: str) -> str:
        """Strips scripts, styles, and extracts dense semantic text."""
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        return text

    def chunk_content(self, raw_html: str) -> List[str]:
        """Cleans and chunks content to stay within token limits."""
        text = self.clean_html(raw_html)
        tokens = self.encoding.encode(text)
        
        chunks = []
        for i in range(0, len(tokens), self.max_tokens):
            chunk_tokens = tokens[i:i + self.max_tokens]
            chunks.append(self.encoding.decode(chunk_tokens))
            
        logger.debug(f"Chunked content into {len(chunks)} parts.")
        return chunks
