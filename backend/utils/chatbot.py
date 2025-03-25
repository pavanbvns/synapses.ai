# backend/utils/chatbot.py

import logging
import threading
import base64
import requests
import json
import time
from backend.utils.config import config

# Configure module-level logger using settings from configuration.
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class ChatBot:
    def __init__(self, model_path: str, inference_engine: str = "llama-server"):
        """
        Initialize the ChatBot.
        If the inference engine is 'llama-server', HTTP calls to the server will be used.
        For local inference, the model is loaded using llama-cpp-python.
        """
        try:
            self.model_path = model_path
            self.inference_engine = inference_engine.lower()
            if self.inference_engine == "llama-server":
                self.model = None
                logger.info("ChatBot configured to use llama-server for inference.")
            else:
                # from llama_cpp import Llama

                # n_ctx = config.get("llama_context", 512)
                # n_gpu_layers = config.get("llama_gpu_layers", 0)
                # self.model = Llama(
                #     model_path=self.model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers
                # )
                logger.info(
                    "Local model loaded successfully from '%s'.", self.model_path
                )
        except Exception as e:
            logger.exception("Error initializing ChatBot: %s", e)
            raise

    def _call_server(
        self, prompt: str, n_predict: int, temperature: float = 0.2
    ) -> str:
        """
        Internal method to call the llama-server completion endpoint.
        """
        try:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = config.get("llama_server_port", 8080)
            endpoint = config.get("llama_server_endpoint", "/completion")
            url = f"http://{llama_host}:{llama_port}{endpoint}"
            payload = {
                "prompt": prompt,
                "n_predict": n_predict,
                "temperature": temperature,
                "seed": 12345,
                "top_k": 40,
                "top_p": 0.9,
            }
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=120)
            elapsed = time.time() - start_time
            logger.info("llama-server responded in %.3f seconds.", elapsed)
            data = response.json()
            generated_text = data.get("completion") or data.get("content")
            if not generated_text:
                logger.error("No generated text found in server response.")
                raise Exception("Server response missing generated text.")
            return generated_text.strip()
        except Exception as e:
            logger.exception("Error calling llama-server: %s", e)
            raise

    def generate_summary(
        self, document_text: str, min_words: int = 50, max_words: int = 150
    ) -> str:
        """
        Generate a summary for the provided document text.
        """
        try:
            # normalized_text = " ".join(document_text.split())
            prompt = (
                f"Summarize the following document in a concise manner using between {min_words} and {max_words} words. "
                f"Return only the summary text without any introductory phrases, headings, commentary, or extra text. "
                f"Document: {document_text}..."
            )
            if self.inference_engine == "llama-server":
                summary = self._call_server(prompt, n_predict=max_words)
            else:
                response = self.model(prompt=prompt, max_tokens=max_words)
                summary = response.get("completion", "").strip()
            logger.info(
                "Generated summary for document of length %d.", len(document_text)
            )
            return summary
        except Exception as e:
            logger.exception("Error generating summary: %s", e)
            raise

    def ask_question(
        self, document_text: str, question: str, response_mode: str
    ) -> str:
        """
        Generate an answer to a question based on the document text.
        If response_mode is 'specific', return only the essential value in a single line in the requested format.
        If response_mode is 'elaborate', return a detailed answer with explanation.
        """
        try:
            normalized_text = " ".join(document_text.split())
            if response_mode.lower() == "specific":
                prompt = (
                    f"Document text: {normalized_text}\n"
                    f"Question: {question}\n"
                    "Extract ONLY the answer"
                    "Do not include any additional commentary or explanations."
                )
                # "Extract ONLY the answer in a single line formatted as: 'The [answer] is [value].' "
            else:
                prompt = (
                    f"Document: {normalized_text}\n"
                    f"Question: {question}\n"
                    "Provide a detailed answer relevant to the question."
                )
            if self.inference_engine == "llama-server":
                answer = self._call_server(prompt, n_predict=200)
            else:
                response = self.model(prompt=prompt, max_tokens=200)
                answer = response.get("completion", "").strip()
            logger.info("Generated answer for question: '%s'.", question)
            return answer
        except Exception as e:
            logger.exception("Error processing question '%s': %s", question, e)
            raise

    def chat(
        self, document_text: str, conversation_history: list, new_message: str
    ) -> str:
        """
        Continue a chat conversation with context based on document text.
        """
        try:
            conversation_history.append(new_message)
            history_text = "\n".join(conversation_history)
            prompt = (
                f"Conversation about the document:\n"
                f"Conversation history:\n{history_text}\n\n"
                f"New message: {new_message}\nResponse:"
            )
            if self.inference_engine == "llama-server":
                chat_response = self._call_server(prompt, n_predict=150)
            else:
                response = self.model(prompt=prompt, max_tokens=150)
                chat_response = response.get("completion", "").strip()
            conversation_history.append(chat_response)
            logger.info("Generated chat response for message: '%s'.", new_message)
            return chat_response
        except Exception as e:
            logger.exception("Error during chat conversation: %s", e)
            raise


class ThreadSafeChatBot(ChatBot):
    """
    A thread-safe wrapper around ChatBot for concurrent operations.
    """

    def __init__(self, model_path: str, inference_engine: str = "llama-server"):
        super().__init__(model_path, inference_engine)
        self.lock = threading.Lock()

    def generate_summary_threadsafe(
        self, document_text: str, min_words: int = 50, max_words: int = 150
    ) -> str:
        with self.lock:
            return self.generate_summary(document_text, min_words, max_words)

    def ask_question_threadsafe(
        self, document_text: str, question: str, response_mode: str = "specific"
    ) -> str:
        with self.lock:
            return self.ask_question(document_text, question, response_mode)

    def chat_threadsafe(
        self, document_text: str, conversation_history: list, new_message: str
    ) -> str:
        with self.lock:
            return self.chat(document_text, conversation_history, new_message)


# Create a global chatbot instance for use across the application.
chatbot_instance = ThreadSafeChatBot(
    model_path=config.get("model_path"), inference_engine="llama-server"
)
