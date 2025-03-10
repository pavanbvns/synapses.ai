import logging
import threading
import base64
import requests
import json
import time
from utils.config import config

# Configure module-level logger based on config settings.
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
        If inference_engine is "llama-server", we'll use HTTP calls to the server.
        Otherwise, for local inference, we'll load the model via llama-cpp-python.
        """
        try:
            self.model_path = model_path
            self.inference_engine = inference_engine.lower()
            if self.inference_engine == "llama-server":
                self.model = None
                logger.info("ChatBot configured to use llama-server for inference.")
            else:
                # Fallback: local inference using llama-cpp-python.
                from llama_cpp import Llama
                n_ctx = config.get("llama_context", 512)
                n_gpu_layers = config.get("llama_gpu_layers", 0)
                self.model = Llama(model_path=self.model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
                logger.info("Local model loaded successfully from '%s'.", self.model_path)
        except Exception as e:
            logger.exception("Error initializing ChatBot: %s", e)
            raise

    def _call_server(self, prompt: str, n_predict: int, temperature: float = 0.7) -> str:
        try:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = config.get("llama_server_port", 8080)
            # The endpoint '/completion' is used by llama-server for generating text.
            endpoint = config.get("llama_server_endpoint", "/completion")
            url = f"http://{llama_host}:{llama_port}{endpoint}"
            payload = {
                "prompt": prompt,
                "n_predict": n_predict,
                "temperature": temperature,
            }
            # logger.debug("Sending prompt to llama-server (first 200 chars): %s", prompt[:200])
            # logger.debug("Payload: %s", json.dumps(payload)[])
            start_time = time.time()
            
            response = requests.post(url, json=payload, timeout=60)
            
            end_time = time.time()
            
            elapsed = end_time - start_time
            
            logger.info("llama-server responded in %.3f seconds.", elapsed)
            # logger.debug("Received response with status code: %s", response.status_code)
            # logger.debug("Response text: %s", response.text)
            data = response.json()
            # logger.debug("Full server response JSON: %s", json.dumps(data, indent=2))
            
            generated_text = data.get("completion") or data.get("content")
            if not generated_text:
                logger.error("No generated text found in server response.")
                raise Exception("Server response missing generated text.")
            return generated_text.strip()
        except Exception as e:
            logger.exception("Error calling llama-server: %s", e)
            raise
        

    def generate_summary(self, document_text: str, min_words: int = 50, max_words: int = 150) -> str:
        """
        Generate a summary for the provided document text.
        """
        try:
            
            document_text_decoded = document_text.decode("utf-8", errors="replace")
            
            # Construct the prompt. Adjust the text truncation as needed.
            prompt = (
                f"Summarize the following document in a concise and coherent manner using between {min_words} and {max_words} words. "
                f"Return only the summary text. Do not include any introductory phrases, headings, commentary, or notes such as 'Note:' or ellipses. "
                f"Do not add any extra text before or after the summary. "
                f"Document: {document_text_decoded}..."
            )
            
            if self.inference_engine == "llama-server":
                summary = self._call_server(prompt, n_predict=max_words)
            else:
                response = self.model(prompt=prompt, max_tokens=max_words)
                summary = response.get("completion", "").strip()
            logger.info("Generated summary for document of length %d characters.", len(document_text))
            return summary
        except Exception as e:
            logger.exception("Error generating summary: %s", e)
            raise

    def ask_question(self, document_text: str, question: str, response_mode: str = "specific") -> str:
        """
        Generate an answer to a question based on the document text.
        """
        try:
            prompt = (
                f"Based on the following document:\n\n{document_text[:1000]}...\n\n"
                f"Answer the following question in a {response_mode} manner:\nQuestion: {question}\nResponse:"
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

    def chat(self, document_text: str, conversation_history: list, new_message: str) -> str:
        """
        Continue a chat conversation with context based on document text.
        """
        try:
            conversation_history.append(new_message)
            history_text = "\n".join(conversation_history)
            prompt = (
                f"The following is a conversation regarding a document.\n"
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
    A thread-safe wrapper around ChatBot for concurrent environments.
    """
    def __init__(self, model_path: str, inference_engine: str = "llama-server"):
        super().__init__(model_path, inference_engine)
        self.lock = threading.Lock()

    def generate_summary_threadsafe(self, document_text: str, min_words: int = 50, max_words: int = 150) -> str:
        with self.lock:
            return self.generate_summary(document_text, min_words, max_words)

    def ask_question_threadsafe(self, document_text: str, question: str, response_mode: str = "specific") -> str:
        with self.lock:
            return self.ask_question(document_text, question, response_mode)

    def chat_threadsafe(self, document_text: str, conversation_history: list, new_message: str) -> str:
        with self.lock:
            return self.chat(document_text, conversation_history, new_message)
