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

from config.settings import get_settings
from services.vector_service import get_vector_service

logger = logging.getLogger(__name__)


class State(TypedDict):
    """State structure for the RAG pipeline."""
    question: str
    context: List[Document]
    answer: str
    retrieval_latency_ms: Optional[int]
    generation_latency_ms: Optional[int]
    retrieved_docs_info: List[dict]


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
            )
            logger.info(f"Using API model: {self.settings.api_model}")
    
    lng = "French"
    def _initialize_prompt_template(self):
        """Initialize the prompt template."""
        template = """
                    You are **Aidly**, the laid-back support specialist at DATAFIRST.
                    You've been here for years and know every feature, quirk, and workaround like the back of your hand.

                    When you reply:
                    - Always reply in {lng}.
                    - Speak like a teammate: warm, casual, and personable.
                    - Vary your greeting: "Hey there!", "Hiya!", "What's up?".
                    - Use empathy and small talk: "Hope you're doing alright," or "Sounds like that caught you off guard."
                    - Paraphrase the user's question back briefly.
                    - Answer directly and confidently—only using information in <context>.
                    - If steps are needed, use clear bullet points or a short numbered list.
                    - If <context> doesn't include the answer, say politely that you don't know and ask for more details (e.g., "Hmm, I don't have enough info from what you've shared. Could you send me more details or a screenshot?").        
                    - If you truly have no idea, say: "Hmm, that's new to me. Can you share a bit more detail?"
                    - Close with an offer to follow up: "Let me know if that helps," or "Give me a shout if you need more."

                    <context>
                    {context}
                    </context>

                    **User:** {question}  
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
        """Retrieve relevant documents for the question."""
        start_time = time.time()
        question = state["question"].lower().strip()
        
        # Check for simple greetings
        greetings = [
            "hey", "hi", "hello", "good morning", "good afternoon", 
            "good evening", "what's up", "how are you", "sup"
        ]
        
        if any(greeting in question for greeting in greetings) and len(question.split()) <= 3:
            logger.info("Simple greeting detected, skipping retrieval")
            retrieval_time = int((time.time() - start_time) * 1000)
            return {
                "context": [],
                "retrieval_latency_ms": retrieval_time,
                "retrieved_docs_info": []
            }
        
        try:
            # Get documents with scores
            retrieved_docs_with_scores = self.vector_service.similarity_search_with_score(
                state["question"], 
                k=self.settings.similarity_search_k
            )
            
            retrieval_time = int((time.time() - start_time) * 1000)
            
            if retrieved_docs_with_scores:
                # Extract documents and prepare info for logging
                context_docs = []
                docs_info = []
                
                for doc, score in retrieved_docs_with_scores:
                    context_docs.append(doc)
                    
                    # Create document info for logging
                    doc_info = {
                        "doc_id": f"{hash(doc.page_content[:100])}",  # Simple hash-based ID
                        "score": float(score),
                        "source": doc.metadata.get("source", "unknown"),
                        "workspace_id": doc.metadata.get("workspace_id")
                    }
                    docs_info.append(doc_info)
                
                logger.info(f"Retrieved {len(context_docs)} documents, best score: {retrieved_docs_with_scores[0][1]}")
                return {
                    "context": context_docs,
                    "retrieval_latency_ms": retrieval_time,
                    "retrieved_docs_info": docs_info
                }
            else:
                logger.warning("No documents retrieved")
                return {
                    "context": [],
                    "retrieval_latency_ms": retrieval_time,
                    "retrieved_docs_info": []
                }
                
        except Exception as e:
            retrieval_time = int((time.time() - start_time) * 1000)
            logger.error(f"Error during retrieval: {e}")
            return {
                "context": [],
                "retrieval_latency_ms": retrieval_time,
                "retrieved_docs_info": []
            }
    
    def _generate(self, state: State) -> dict:
        """Generate an answer based on the question and context."""
        start_time = time.time()
        
        try:
            # Prepare context text
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
                "lng": "French"
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
    
    def ask_question(self, question: str) -> Tuple[str, dict]:
        """
        Process a question through the RAG pipeline and return the answer with metrics.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple of (answer, metrics_dict) where metrics contains:
            - retrieval_latency_ms
            - generation_latency_ms
            - retrieved_docs_info
            - model_name
        """
        if not question or not question.strip():
            return "I didn't receive a question. Could you please ask something?", {}
        
        try:
            logger.info(f"Processing question: {question[:100]}...")
            
            result = self.rag_graph.invoke({"question": question})
            answer = result.get("answer", "I wasn't able to generate an answer.")
            
            # Collect metrics
            metrics = {
                "retrieval_latency_ms": result.get("retrieval_latency_ms"),
                "generation_latency_ms": result.get("generation_latency_ms"),
                "retrieved_docs_info": result.get("retrieved_docs_info", []),
                "model_name": self.settings.local_model if self.settings.is_local else self.settings.api_model,
                "temperature": None,  # Could be added to LLM config
                "num_retrieved": len(result.get("retrieved_docs_info", []))
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
    rag_service = get_rag_service()
    
    logger.info("RAG system initialization completed") 