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
        self,
        prompt: str,
        #  n_predict: int,
        temperature: float,
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
                "n_predict": 512,
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

    def _call_server_streaming(
        self,
        prompt: str,
        # n_predict: int = 200,
        temperature: float,
    ):
        """
        Streaming generator that yields partial text from llama-server in chunks.
        This requires that your llama-server supports chunked or SSE responses.
        """
        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = config.get("llama_server_port", 8080)
        endpoint = config.get("llama_server_endpoint", "/completion")
        url = f"http://{llama_host}:{llama_port}{endpoint}"

        payload = {
            "prompt": prompt,
            "n_predict": 512,
            "temperature": temperature,
            "seed": 12345,
            "top_k": 40,
            "top_p": 0.9,
            "stream": True,  # your llama-server would need to respect this param
        }

        try:
            with requests.post(url, json=payload, stream=True, timeout=300) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        text_chunk = chunk.decode("utf-8", errors="ignore")
                        yield text_chunk
        except Exception as e:
            logger.exception(f"Error in streaming from llama-server: {e}")
            yield f"\n[ERROR] {str(e)}\n"

    def generate_summary(
        self, document_text: str, min_words: int = 50, max_words: int = 150
    ) -> str:
        """
        Generate a summary for the provided document text.
        """
        try:
            # normalized_text = " ".join(document_text.split())
            # prompt = (
            #     f"Summarize the following document in a concise manner using between {min_words} and {max_words} words. "
            #     f"Return only the summary text without any introductory phrases, headings, commentary, or extra text. "
            #     f"Document: {document_text}..."
            # )
            prompt = f"""

            You are an expert content summarizer. You take content in and output only a summary.

            Combine all of your understanding of the content and Summarize the content into a concise summary between {min_words} and {max_words} words.
            Summarize the content completely and VERY IMPORTANTLY ensure that the summary is LOGICAL, RELEVANT and NOT truncated
            You only output human readable Markdown.
            Do NOT output introductory phrases, headings, commentary,extra text, warnings or notes. Return the requested summary ONLY.
            Do NOT repeat items in the summary.
            Do NOT start items with the same opening words.
            
            INPUT: \n{document_text}"""

            if self.inference_engine == "llama-server":
                summary = self._call_server(
                    prompt,
                    # n_predict=max_words,
                    temperature=0.7,
                )
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
        If response_mode is 'specific', return ONLY the essential value in a single line in the requested format.
        If response_mode is 'elaborate', return a detailed answer with explanation.
        """
        try:
            normalized_text = " ".join(document_text.split())
            if response_mode.lower() == "specific":
                prompt = f"""
                    Document text: {normalized_text}\n"
                    Question: {question}\n"
                    You are an expert content analyzer and can accurately generate an answer to a question based on the document text relevant to the question asked.
                    Return ONLY the essential value in a single line, in the requested format.
                    You only output human-readable Markdown.
                    Do NOT output any introductory phrases, headings, commentary, extra text, warnings, or notes.
                    Do NOT repeat items in the answer.
                    Do NOT start items with the same opening words.
                    Answer the question based ONLY on the information provided in the document text.
                    If the answer is explicitly stated in the document, provide the answer DIRECTLY and stop.
                    If the answer requires inference or summarization of information within the document, provide a concise and accurate response DIRECTLY and stop.
                    If the answer cannot be found within the provided document text, output: 'Answer not found in document.' and stop.
                    Do NOT include any external information or assumptions beyond what is present in the document.
                    Output the answer DIRECTLY, without any prefixes, labels, or additional text.
                    """
                # "Extract ONLY the answer in a single line formatted as: 'The [answer] is [value].' "
            else:
                prompt = f"""
                    Document text: {normalized_text}\n
                    Question: {question}\n
                    You are an expert content analyzer and can accurately generate an answer to a question based on the document text relevant to the question asked.
                    Return a detailed answer with necessary and relevant explanation.
                    If the answer is explicitly stated in the document, provide the answer directly.
                    If the answer requires inference or summarization of information within the document, provide a concise and accurate response.
                    You only output human readable Markdown.
                    Do NOT output introductory phrases, headings, commentary,extra text, warnings or notes. Return the requested answer ONLY.
                    Do NOT repeat items in the answer.
                    Do NOT start items with the same opening words.
                    Answer the question based ONLY on the information provided in the document text.
                    If the answer cannot be found within the provided document text, state: 'Answer not found in document.' and stop.
                    Do not include any external information or assumptions beyond what is present in the document.
                    Provide the answer directly."""

            if self.inference_engine == "llama-server":
                answer = self._call_server(
                    prompt,
                    temperature=0.2,
                    #    , n_predict=200
                )
            else:
                response = self.model(prompt=prompt, max_tokens=200)
                answer = response.get("completion", "").strip()
            logger.info("Generated answer for question: '%s'.", question)
            return answer
        except Exception as e:
            logger.exception("Error processing question '%s': %s", question, e)
            raise

    def stream_chat(self, combined_context: str, user_query: str):
        """
        Streaming chat. Yields partial tokens.
        """
        prompt = (
            f"Context:\n{combined_context}\n\n"
            f"User query: {user_query}\n\n"
            "Answer (streaming partial tokens):"
        )
        return self._call_server_streaming(prompt, temperature=0.2)

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
                chat_response = self._call_server(
                    prompt,
                    temperature=0.2,
                    #   , n_predict=150
                )
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
