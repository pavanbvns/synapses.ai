# backend/utils/chatbot.py

import logging
import threading
import requests
import time
from backend.utils.config import config

# Setup logger
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class ChatBot:
    def __init__(self, model_path: str, inference_engine: str = "llama-server"):
        try:
            self.model_path = model_path
            self.inference_engine = inference_engine.lower()
            if self.inference_engine != "llama-server":
                raise ValueError("Only llama-server is supported for inference.")
            logger.info("ChatBot initialized for llama-server inference.")
        except Exception as e:
            logger.exception("Failed to initialize ChatBot: %s", e)
            raise

    def _call_llama_server(
        self, prompt: str, temperature: float = 0.7, stream: bool = False
    ):
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
            "stream": stream,
        }

        try:
            if stream:
                with requests.post(
                    url, json=payload, stream=True, timeout=300
                ) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            yield chunk.decode("utf-8", errors="ignore")
            else:
                start = time.time()
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                duration = time.time() - start
                logger.info("llama-server responded in %.2f seconds", duration)
                data = response.json()
                return data.get("completion") or data.get("content")
        except Exception as e:
            logger.exception("Error calling llama-server: %s", e)
            if stream:
                yield f"\n[ERROR] {str(e)}\n"
            else:
                raise

    def generate_summary(
        self, document_text: str, min_words: int = 50, max_words: int = 150
    ) -> str:
        try:
            prompt = f"""

            You are an expert content summarizer. You take content in and output only a summary.

            Combine all of your understanding of the content and Summarize the content into a concise summary between {min_words} and {max_words} words.
            Summarize the content completely and VERY IMPORTANTLY ensure that the summary is LOGICAL, RELEVANT and NOT truncated
            You only output human readable Markdown.
            Do NOT output introductory phrases, headings, commentary,extra text, warnings or notes. Return the requested summary ONLY.
            Do NOT repeat items in the summary.
            Do NOT start items with the same opening words.

            INPUT: \n{document_text}"""
            # return self._call_llama_server(prompt, temperature=0.7).strip()
            return self._call_llama_server(prompt, temperature=0.7)
        except Exception as e:
            logger.exception("Error generating summary: %s", e)
            raise

    def ask_question(
        self, document_text: str, question: str, response_mode: str
    ) -> str:
        try:
            normalized_text = " ".join(document_text.split())

            if response_mode.lower() == "specific":
                prompt = f"""
                Document text: {normalized_text}
                Question: {question}
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
            else:
                prompt = f"""
                Document text: {normalized_text}
                Question: {question}
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
                Provide the answer directly.
                """

            return self._call_llama_server(prompt, temperature=0.2).strip()
        except Exception as e:
            logger.exception("Error answering question '%s': %s", question, e)
            raise

    def chat(
        self, document_text: str, conversation_history: list, new_message: str
    ) -> str:
        try:
            conversation_history.append(new_message)
            history_text = "\n".join(conversation_history)
            prompt = (
                f"Conversation about the document:\n"
                f"Conversation history:\n{history_text}\n\n"
                f"New message: {new_message}\nResponse:"
            )
            response = self._call_llama_server(prompt, temperature=0.2)
            response = response.strip()
            conversation_history.append(response)
            return response
        except Exception as e:
            logger.exception("Chat failure: %s", e)
            raise

    def stream_chat(self, combined_context: str, user_query: str):
        try:
            prompt = (
                f"Context:\n{combined_context}\n\n"
                f"User query: {user_query}\n\n"
                "Answer (streaming partial tokens):"
            )
            return self._call_llama_server(prompt, temperature=0.2, stream=True)
        except Exception as e:
            logger.exception("Error during stream chat: %s", e)
            yield f"\n[ERROR] {str(e)}\n"


class ThreadSafeChatBot(ChatBot):
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


# Global singleton chatbot instance
chatbot_instance = ThreadSafeChatBot(
    model_path=config.get("model_path"), inference_engine="llama-server"
)
