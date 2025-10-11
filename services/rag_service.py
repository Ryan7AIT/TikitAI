"""
RAG service for managing the retrieval-augmented generation pipeline.
"""
import logging
import time
from typing import List, Optional, Tuple

from langchain_community.chat_models import ChatOllama
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from sqlmodel import Session, select

from config.settings import get_settings
from services.vector_service import get_vector_service
from db import get_session
from models import UserPreference
from translator import translate_text

logger = logging.getLogger(__name__)


class State(TypedDict):
    """State structure for the RAG pipeline."""
    question: str
    original_question: str  # Original question before translation
    translated_question: Optional[str]  # Question after translation (used for search)
    context: List[Document]
    answer: str
    retrieval_latency_ms: Optional[int]
    generation_latency_ms: Optional[int]
    retrieved_docs_info: List[dict]
    workspace_id: Optional[int]
    language: str  # User's preferred language for response
    source_language: str  # Detected/configured source language of the question
    was_translated: bool  # Whether translation occurred


class RAGService:
    """Service for managing the RAG pipeline."""
    
    def __init__(self):
        self.settings = get_settings()
        self.vector_service = get_vector_service()
        self._llm = None
        self._prompt_template = None
        self._rag_graph = None
        
    @property
    def llm(self):
        """Get or create the language model."""
        if self._llm is None:
            self._initialize_llm()
        return self._llm
    
    @property
    def prompt_template(self) -> PromptTemplate:
        """Get or create the prompt template."""
        if self._prompt_template is None:
            self._initialize_prompt_template()
        return self._prompt_template
    
    @property
    def rag_graph(self):
        """Get or create the RAG graph."""
        if self._rag_graph is None:
            self._initialize_rag_graph()
        return self._rag_graph
    
    def _initialize_llm(self):
        """Initialize the language model based on configuration."""
        logger.info("Initializing language model...")
        
        if self.settings.is_local:
            self._llm = ChatOllama(model=self.settings.local_model)
            logger.info(f"Using local model: {self.settings.local_model}")
        else:
            if not self.settings.google_api_key:
                raise ValueError("Google API key is required for non-local models")
                
            self._llm = init_chat_model(
                model=self.settings.api_model,
                model_provider="google_genai",
                api_key=self.settings.google_api_key,
                temperature=0.4,
            )
            logger.info(f"Using API model: {self.settings.api_model}")
    
    def _initialize_prompt_template(self):
        """Initialize the prompt template."""

        template = """
            You are **Aidly**, the laid-back support specialist at DATAFIRST.

            **CRITICAL: Only use information from <context> that directly answers the user's question. If the context doesn't contain relevant information, say you don't know.**

            <context>
            {context}
            </context>

            **User Question:** {question}

            **INTERNAL REASONING (DO NOT SHOW TO USER):**
            1. Check if the context contains information that directly answers this question
            2. If yes, use only that relevant information to answer
            3. If no, politely say you don't have enough information

            **RESPONSE FORMAT - Follow these guidelines for your final answer:**
            - Always reply in {lng}
            - Sound casual and friendly: "Hey there!", "Hiya!", "What's up?"
            - Briefly restate what you understand they're asking
            - Only answer with information that's actually relevant to their question
            - If context doesn't help: "Hmm, I don't see info about that in what I have access to. Could you give me more details?"
            - Close warmly: "Hope that helps!", "Let me know if you need more!"
            - **NEVER show your reasoning steps or mention "Step 1", "Step 2", etc. in your response**

            **Aidly:**
            """
        
        self._prompt_template = PromptTemplate(
            input_variables=["context", "question", "lng"],
            template=template,
        )
        logger.info("Prompt template initialized")
    
    def _initialize_rag_graph(self):
        """Initialize the RAG graph pipeline."""
        logger.info("Initializing RAG graph...")
        
        graph_builder = StateGraph(State)
        graph_builder.add_node("retrieve", self._retrieve)
        graph_builder.add_node("generate", self._generate)
        graph_builder.add_edge(START, "retrieve")
        graph_builder.add_edge("retrieve", "generate")
        self._rag_graph = graph_builder.compile()
        
        logger.info("RAG graph initialized")
    
    def _retrieve(self, state: State) -> dict:
        """
        Retrieve relevant documents for the question.
        
        This method handles translation of non-English queries to English before
        performing semantic search, ensuring all searches are conducted in English
        for consistency and better retrieval accuracy.
        """
        start_time = time.time()
        original_question = state["question"]
        question = state["question"].lower().strip()
        
        # Static responses for demo purposes
        static_responses = {
            # Greetings
            "hello": "Hey there! 👋",
            "hi": "Hey!, I'm Aidly, your friendly support specialist at DATAFIRST! 😊. How can I assist you today?",
            "hey": "Hey!, I'm Aidly, your friendly support specialist at DATAFIRST! 😊. How can I assist you today?",
            "how can i change the supervisor of a zone?": "To change the supervisor of a zone, you can navigate to the zone settings in your Admin application and select a new supervisor from the list of available users. If you need more detailed instructions, please let me know!",
            "where can i find the objective statistics report?": "You can find the Objective Statistics Report in the statistics section of your Admin application. By choosing the type of statistics **Objective** and then selecting the desired parameters, you can generate the report. If you need further assistance, feel free to ask! 😊",
            "good morning": "Good morning! Hope you're having a great day!",
            "good afternoon": "Good afternoon! What's up?",
            "good evening": "Good evening!",
            "what's up": "Hey! Just here to help you out. What do you need?",
            "how are you": "I'm doing great, thanks for asking! How can I help you today?",
            
            # Common demo questions
            "who are you": "I'm Aidly, your friendly support specialist at DATAFIRST! 😊",
            "what can you do": "I can help you find information from your documents and answer questions about your workspace. Just ask me anything!",
            "help": "Sure thing! I'm here to help you find information. Try asking me about your documents or any specific topic you need help with.",
            "test": "Test successful! I'm working perfectly. What would you like to know?",
            
            # Add more static responses as needed
        }
        
        # Check for exact matches first
        if question in static_responses:
            logger.info(f"Static response triggered for: {question}")
            retrieval_time = int((time.time() - start_time) * 1000)
            # Create a fake document with the static response
            static_doc = Document(
                page_content=static_responses[question],
                metadata={"source": "static_response", "type": "greeting"}
            )
            return {
                "context": [static_doc],
                "retrieval_latency_ms": retrieval_time,
                "retrieved_docs_info": [{
                    "doc_id": "static",
                    "doc": static_responses[question],
                    "score": 1.0,
                    "source": "static_response",
                    "workspace_id": "demo"
                }]
            }
        
        # Check for simple greetings (fallback)
        greetings = [
            "hey", "hi", "hello", "good morning", "good afternoon", 
            "good evening", "what's up", "how are you", "sup"
        ]
        
        if any(greeting in question for greeting in greetings) and len(question.split()) <= 3:
            logger.info("Simple greeting detected, using default greeting response")
            retrieval_time = int((time.time() - start_time) * 1000)
            static_doc = Document(
                page_content="Hey! What can I help you with today?",
                metadata={"source": "static_response", "type": "greeting"}
            )
            return {
                "context": [static_doc],
                "retrieval_latency_ms": retrieval_time,
                "retrieved_docs_info": [{
                    "doc_id": "static_greeting",
                    "doc": "Hey! What can I help you with today?",
                    "score": 1.0,
                    "source": "static_response",
                    "workspace_id": "demo"
                }]
            }
        
        try:
            # Translate question to English if needed
            # We always search in English for consistency
            search_question = state["question"]
            source_lang = state.get("source_language", "en")
            
            # Only translate if source language is not English
            if source_lang != "en" and source_lang.lower() != "english":
                try:
                    logger.info(f"Translating question from {source_lang} to English: {state['question'][:50]}...")
                    search_question = translate_text(
                        state["question"], 
                        source=source_lang, 
                        target="en"
                    )
                    logger.info(f"Translated question: {search_question[:50]}...")
                except Exception as e:
                    logger.error(f"Translation failed, using original question: {e}")
                    search_question = state["question"]

            # Get documents with scores, filtering by workspace_id
            metadata_filter = None
            if state.get("workspace_id"):
                metadata_filter = {"metadata.workspace_id": state["workspace_id"]}
            
            # Use the translated (English) question for search
            retrieved_docs_with_scores = self.vector_service.similarity_search_with_score(
                search_question, 
                k=self.settings.similarity_search_k,
                metadata_filter=metadata_filter
            )

            print(f"Retrieved {retrieved_docs_with_scores} documents")
            
            retrieval_time = int((time.time() - start_time) * 1000)
            
            if retrieved_docs_with_scores:
                # Extract documents and prepare info for logging
                context_docs = []
                docs_info = []
                
                for doc, score in retrieved_docs_with_scores:

                    if score > 0.6:  # Threshold to filter out low-relevance docs
                        context_docs.append(doc)

                    
                    # Create document info for logging
                    doc_info = {
                        "doc_id": doc.metadata.get("_id", "unknown"),
                        "doc": doc.page_content,
                        "score": float(score),
                        "source": doc.metadata.get("source", "unknown"),
                        "workspace_id": doc.metadata.get("workspace_id", "unknown")
                    }
                    docs_info.append(doc_info)
                
                logger.info(f"Retrieved {len(context_docs)} documents, best score: {retrieved_docs_with_scores[0][1]}")
                return {
                    "context": context_docs,
                    "retrieval_latency_ms": retrieval_time,
                    "retrieved_docs_info": docs_info,
                    "translated_question": search_question  # Return the translated question
                }
            else:
                logger.warning("No documents retrieved")
                return {
                    "context": [],
                    "retrieval_latency_ms": retrieval_time,
                    "retrieved_docs_info": [],
                    "translated_question": search_question  # Return the translated question
                }
                
        except Exception as e:
            retrieval_time = int((time.time() - start_time) * 1000)
            logger.error(f"Error during retrieval: {e}")
            return {
                "context": [],
                "retrieval_latency_ms": retrieval_time,
                "retrieved_docs_info": [],
                "translated_question": state["question"]  # Return original if error
            }
    
    def _generate(self, state: State) -> dict:
        """Generate an answer based on the question and context."""
        start_time = time.time()
        
        try:
            # Check if this is a static response
            if (state["context"] and len(state["context"]) == 1 and 
                state["context"][0].metadata.get("source") == "static_response"):
                # Add a 1-second delay for demo purposes to simulate thinking
                time.sleep(1)
                # Return the static response directly
                generation_time = int((time.time() - start_time) * 1000)
                logger.info("Returning static response directly (with 1s delay)")
                return {
                    "answer": state["context"][0].page_content,
                    "generation_latency_ms": generation_time
                }
            
            # Prepare context text for regular responses
            if state["context"]:
                docs_content = "\n\n".join(doc.page_content for doc in state["context"])
                context_text = f"Here's what I know that might be relevant:\n\n{docs_content}\n\n"
                logger.info(f"Using context from {len(state['context'])} documents")
            else:
                context_text = ""
                logger.info("No context available, generating without retrieval")
            
            # Generate response
            messages = self.prompt_template.invoke({
                "question": state["question"], 
                "context": context_text,
                "lng": state["language"]
            })
            response = self.llm.invoke(messages)
            
            generation_time = int((time.time() - start_time) * 1000)
            
            return {
                "answer": response.content,
                "generation_latency_ms": generation_time
            }
            
        except Exception as e:
            generation_time = int((time.time() - start_time) * 1000)
            logger.error(f"Error during generation: {e}")
            return {
                "answer": "I'm having trouble processing your question right now. Please try again.",
                "generation_latency_ms": generation_time
            }
    
    def ask_question(self, question: str, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> Tuple[str, dict]:
        """
        Process a question through the RAG pipeline and return the answer with metrics.
        
        This method handles:
        1. Fetching user's language preference from the database
        2. Translating non-English questions to English for retrieval
        3. Generating responses in the user's preferred language
        4. Tracking translation metrics for logging
        
        Args:
            question: The user's question (in any supported language)
            workspace_id: The workspace ID to filter documents by (optional)
            user_id: The user ID to fetch language preference (optional)
            
        Returns:
            Tuple of (answer, metrics_dict) where metrics contains:
            - retrieval_latency_ms
            - generation_latency_ms
            - retrieved_docs_info
            - model_name
            - source_language: detected/configured language of input
            - response_language: language of response
            - was_translated: whether translation occurred
            - original_question: question before translation
            - translated_question: question after translation (for search)
        """
        print("-------------------------------------------------------------------------")
        print("-------------------------------------------------------------------------")

        print("ask_question called")
        print(f"Question: {question[:50]}...")
        print("-------------------------------------------------------------------------")
        print("-------------------------------------------------------------------------")

        if not question or not question.strip():
            return "I didn't receive a question. Could you please ask something?", {}
        
        # Get user's language preference for both source and response
        response_language = "English"  # Language for response (default)
        source_language = "en"  # Language code for source question (default)
        
        if user_id:
            try:
                session = next(get_session())
                try:
                    stmt = select(UserPreference).where(
                        UserPreference.user_id == user_id,
                        UserPreference.preference == "language"
                    )
                    pref = session.exec(stmt).first()
                    if pref:
                        # Map language codes to full names for response
                        language_map = {
                            "en": "English",
                            "fr": "French",
                            "ar": "Arabic",
                        }
                        # Store both the code (for translation) and full name (for response)
                        source_language = pref.value.lower()
                        response_language = language_map.get(source_language, pref.value)
                        logger.info(f"Using language preference for user {user_id}: {response_language} (code: {source_language})")
                    else:
                        logger.info(f"No language preference found for user {user_id}, using default: {response_language}")
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Error fetching language preference for user {user_id}: {e}")
        
        try:
            logger.info(f"Processing question: {question[:100]}... (response language: {response_language}, source language: {source_language})")
            if workspace_id:
                logger.info(f"Filtering by workspace_id: {workspace_id}")
            
            # Invoke RAG graph with all necessary parameters
            result = self.rag_graph.invoke({
                "question": question,
                "original_question": question,  # Store original for logging
                "workspace_id": workspace_id,
                "language": response_language,  # Language for response generation
                "source_language": source_language,  # Language of input question
                "was_translated": source_language != "en"  # Track if translation will occur
            })

            answer = result.get("answer", "I wasn't able to generate an answer.")
            
            # Collect metrics including translation information
            metrics = {
                "retrieval_latency_ms": result.get("retrieval_latency_ms"),
                "generation_latency_ms": result.get("generation_latency_ms"),
                "retrieved_docs_info": result.get("retrieved_docs_info", []),
                "model_name": self.settings.local_model if self.settings.is_local else self.settings.api_model,
                "temperature": None,  # Could be added to LLM config
                "num_retrieved": len(result.get("retrieved_docs_info", [])),
                # Translation metrics
                "source_language": source_language,
                "response_language": response_language,
                "was_translated": source_language != "en",
                "original_question": question,
                "translated_question": result.get("translated_question") if source_language != "en" else None
            }
            
            logger.info("Question processed successfully")
            return answer, metrics
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return "I'm having trouble processing your question right now. Please try again.", {}


# Global RAG service instance
rag_service = RAGService()


def get_rag_service() -> RAGService:
    """Get the global RAG service instance."""
    return rag_service


def initialize_rag_system():
    """Initialize the complete RAG system."""
    logger.info("Initializing RAG system...")
    
    # Initialize vector service and load documents
    vector_service = get_vector_service()
    vector_service.load_documents_from_data_folder()
    
    # Initialize RAG service (lazy initialization will handle the rest)
    get_rag_service()
    
    logger.info("RAG system initialization completed") 