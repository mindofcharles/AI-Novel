import os
import logging
from typing import Optional

# Conditional import for the new Google GenAI SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

import config


class LLMClientError(RuntimeError):
    """Raised when generation client calls fail."""


class LLMClient:
    def __init__(
        self,
        model_type: str = config.PRIMARY_MODEL_TYPE,
        model_name: Optional[str] = None,
        enable_embedding: bool = True
    ):
        self.model_type = model_type
        self.model_name = model_name
        
        # Generation Clients
        self.gemini_client = None
        self.openai_client = None
        
        # Embedding Client (Separate)
        self.openai_embedding_client = None
        
        self.logger = logging.getLogger("LLMClient")
        
        # Setup Generation Client
        if self.model_type == "gemini":
            self._setup_gemini()
        elif self.model_type == "openai":
            self._setup_openai()
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
            
        # Setup Embedding Client
        if enable_embedding:
            self._setup_embedding()

    def _setup_gemini(self):
        if not genai:
            self.logger.error("google-genai package not installed. Please pip install google-genai")
            return
        
        api_key = config.GEMINI_API_KEY
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            self.logger.warning("Gemini API Key not found in config or environment.")
            return

        # Initialize the new Client
        self.gemini_client = genai.Client(api_key=api_key)

    def _setup_openai(self):
        if not OpenAI:
            self.logger.error("openai package not installed. Please pip install openai")
            return
            
        try:
            self.openai_client = OpenAI(
                base_url=config.OPENAI_BASE_URL,
                api_key=config.OPENAI_API_KEY
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")

    def _setup_embedding(self):
        """Sets up the dedicated client for embeddings."""
        if config.EMBEDDING_PROVIDER == "openai":
            if not OpenAI:
                self.logger.error("openai package not installed. Cannot setup OpenAI embeddings.")
                return
            try:
                self.openai_embedding_client = OpenAI(
                    base_url=config.EMBEDDING_BASE_URL,
                    api_key=config.EMBEDDING_API_KEY
                )
                self.logger.info(f"Initialized OpenAI Embedding Client at {config.EMBEDDING_BASE_URL}")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI Embedding client: {e}")
        elif config.EMBEDDING_PROVIDER == "gemini":
            # Gemini typically reuses the same client/auth for both generation and embeddings
            # If the generation client isn't set up yet (e.g. we are using OpenAI for generation but Gemini for embeddings), we need to set it up.
            if not self.gemini_client:
                self._setup_gemini()

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.7) -> str:
        """
        Unified generation method.
        """
        if self.model_type == "gemini":
            return self._generate_gemini(prompt, system_instruction, temperature)
        elif self.model_type == "openai":
            return self._generate_openai(prompt, system_instruction, temperature)
        return ""

    def _generate_gemini(self, prompt: str, system_instruction: str, temperature: float) -> str:
        if not self.gemini_client:
            raise LLMClientError("Gemini client not initialized.")
        
        try:
            # The new SDK uses client.models.generate_content
            # Config is passed differently
            
            config_args = {
                "temperature": temperature
            }
            
            # Prepare arguments
            kwargs = {
                "model": self.model_name or config.GEMINI_MODEL_NAME,
                "contents": prompt,
                "config": config_args
            }

            # System instruction is a direct parameter in the new SDK
            if system_instruction:
                kwargs["config"]["system_instruction"] = system_instruction

            response = self.gemini_client.models.generate_content(**kwargs)
            return response.text
        except Exception as e:
            self.logger.error(f"Gemini generation error: {e}")
            raise LLMClientError(f"Gemini generation failed: {e}") from e

    def _generate_openai(self, prompt: str, system_instruction: str, temperature: float) -> str:
        if not self.openai_client:
            raise LLMClientError("OpenAI client not initialized.")

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_name or config.OPENAI_MODEL_NAME,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI generation error: {e}")
            raise LLMClientError(f"OpenAI generation failed: {e}") from e

    def get_embedding(self, text: str) -> Optional[list]:
        """
        Get embedding for vector search using the dedicated embedding configuration.
        """
        provider = config.EMBEDDING_PROVIDER

        if provider == "gemini":
            if not self.gemini_client: 
                self.logger.error("Gemini client not initialized for embeddings.")
                return None
            try:
                result = self.gemini_client.models.embed_content(
                    model=config.GEMINI_EMBEDDING_MODEL,
                    contents=text,
                    config={"task_type": "RETRIEVAL_DOCUMENT"}
                )
                return result.embeddings[0].values
            except Exception as e:
                self.logger.error(f"Gemini embedding error: {e}")
                return None
                
        elif provider == "openai":
            if not self.openai_embedding_client:
                self.logger.error("OpenAI Embedding client not initialized.")
                return None
            try:
                response = self.openai_embedding_client.embeddings.create(
                    model=config.EMBEDDING_MODEL_NAME,
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                self.logger.error(f"OpenAI embedding error: {e}")
                return None
        
        self.logger.error(f"Unknown Embedding Provider: {provider}")
        return None
