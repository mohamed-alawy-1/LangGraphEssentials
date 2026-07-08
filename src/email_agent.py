import os
import uuid
from typing import Literal, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import Client

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Define structural TypeDict schemas for the Email Classification details
class EmailClassification(TypedDict):
    category: Literal["spam", "ham"]
    urgency: Literal["low", "medium", "high", "critical"]
    confidence: float
    summary: str


# Define the global Email Agent state schema
class EmailAgentState(TypedDict):
    email_content: str
    email_subject: str
    email_sender: str
    email_id: str
    classification: EmailClassification | None
    search_results: list[str] | None
    draft_response: str | None


# Initialize the LLM client (using ChatOpenAI configured via environment variables)
api_key=os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gemini-2.5-flash-lite",
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=api_key,
)

# Initialize LangSmith client for tracing and logging
client = Client()
classification_prompt = client.pull_prompt(
    "email_classifier",
    include_model=True,
    secrets={"OPENAI_API_KEY": api_key}
)

draft_prompt = client.pull_prompt(
    "draft_prompt",
    include_model=True,
    secrets={"OPENAI_API_KEY": api_key}
)


def read_email_content(state: EmailAgentState) -> EmailAgentState:
    """Extracts or pre-processes the content of an email (Placeholder node)."""
    return state


def classify_email(state: EmailAgentState) -> EmailAgentState:
    """Analyses and classifies email metadata & content using the LLM with structured output."""
    # structured_llm = llm.with_structured_output(EmailClassification, method="json_mode")
#     classification_prompt = f"""
# You are an email classification agent. Your task is to classify the following email content into a category (spam or ham),
# determine its urgency level (low, medium, high, critical), and provide a confidence score (between 0 and 1).and provide a brief summary.

# Email Content: {state['email_content']}
# Email Subject: {state['email_subject']}
# From: {state['email_sender']}

# Please provide the output in the following JSON format:

# {{
#     "category": "spam or ham",
#     "urgency": "low, medium, high, critical",
#     "confidence": 0.0,
#     "summary": "brief summary of the email"
# }}
# """
    # classification = structured_llm.invoke(classification_prompt)

    classification = classification_prompt.invoke(
        {
            "email_content": state['email_content'], 
            "email_subject": state['email_subject'], 
            "email_sender": state['email_sender']
         }
    )
    state["classification"] = classification
    return state


def search_documents(state: EmailAgentState) -> EmailAgentState:
    """Mock node: Simulates searching internal documents/knowledge base for email context."""
    classification = state.get("classification", None)
    # Simulate a document search query result set
    search_results = [
        f"Document {i+1} referencing: {state['email_content'][:30]} (Class: {classification.get('category') if classification else 'N/A'})"
        for i in range(3)
    ]
    state["search_results"] = search_results
    return state


def write_draft_response(state: EmailAgentState) -> Command[Literal["review_draft", "send_reply"]]:
    """Drafts a reply based on classification results and flags for review if category/urgency conditions are met."""
    classification = state.get("classification") or {}
    search_results = state.get("search_results") or []

#     draft_prompt = f"""
# You are an email response agent. Based on the following email content, its classification, and the search results,
# please draft a professional response to the email.

# Email Content: {state['email_content']}
# Classification: {classification.get('category', 'N/A')}
# urgency: {classification.get('urgency', 'medium')}
# Search Results: {search_results}

# Please provide a concise and professional draft response. Do NOT include any "Subject:" line, headers, salutations to headers, or subject lines in your draft response. Just output the body of the email reply directly.
# """
#     draft_response = llm.invoke(draft_prompt)

    draft_response = draft_prompt.invoke(
        {
            "email_content": state['email_content'], 
            "category": classification.get("category", "N/A"),
            "urgency": classification.get("urgency", "medium"),
            "search_results": search_results
         }
    )
    
    # Human interaction criteria: Require review if spam OR high/critical urgency
    needs_review = (
        classification.get("urgency") in ["high", "critical"]
        or classification.get("category") == "spam"
    )

    if needs_review:
        goto = "review_draft"
        print(f"[{state['email_id']}] Review Required! Routing to human-in-the-loop review node.")
    else:
        goto = "send_reply"

    return Command(
        update={"draft_response": draft_response.content}, goto=goto
    )


def review_draft(state: EmailAgentState) -> Command[Literal["send_reply", END]]:
    """Pauses graph execution to request human (admin) feedback and edits for sensitive drafts."""
    classification = state.get("classification") or {}

    # Trigger human-in-the-loop interrupt with current state facts
    human_decision = interrupt(
        {
            "email_sender": state["email_sender"],
            "email_subject": state["email_subject"],
            "email_content": state["email_content"],
            "draft_response": state["draft_response"],
            "category": classification.get("category", "N/A"),
            "urgency": classification.get("urgency", "medium"),
            "action": "Please review the draft response. Approve or supply an edited response.",
        }
    )

    # Process human response input from the checkpoint resume trigger
    if human_decision.get("approved"):
        edited = human_decision.get("edited_response") or state["draft_response"]
        return Command(update={"draft_response": edited}, goto="send_reply")
    else:
        print(f"[{state['email_id']}] Draft rejected by reviewer. Terminating workflow.")
        return Command(update={}, goto=END)


def send_reply(state: EmailAgentState) -> EmailAgentState:
    """Mock node: Simulates sending out the finalized email reply to the sender."""
    print(
        f"\n>>> SENDING Reply to: {state['email_sender']}\n"
        f"Subject: Re: {state['email_subject']}\n"
        f"Body:\n{state['draft_response']}\n"
    )
    return {}


# Construct and compile the full StateGraph workflow
def build_graph(checkpointer: InMemorySaver) -> StateGraph:
    builder = StateGraph(EmailAgentState)

    # Register workflow nodes
    builder.add_node("read_email", read_email_content)
    builder.add_node("classify_email", classify_email)
    builder.add_node("search_documents", search_documents)
    builder.add_node("write_draft_response", write_draft_response)
    builder.add_node("review_draft", review_draft)
    builder.add_node("send_reply", send_reply)

    # Define standard state transitions
    builder.add_edge(START, "read_email")
    builder.add_edge("read_email", "classify_email")
    builder.add_edge("classify_email", "search_documents")
    builder.add_edge("search_documents", "write_draft_response")
    builder.add_edge("send_reply", END)

    # Compile with memory checkpoint capability to support thread interrupts
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    memory = InMemorySaver()
    app = build_graph(checkpointer=memory)

    # Set of test emails to showcase regular execution and interrupt-handling
    test_emails = [
        "Hello there! I was asking about the new product launch.",
        "Get a free gift card by clicking this link!",
    ]

    for i, content in enumerate(test_emails):
        email_payload = {
            "email_content": content,
            "email_subject": f"Inquiry #{i}",
            "email_sender": "mohamed@gmail.com",
            "email_id": f"email_{i}",
        }

        thread_id = uuid.uuid4()
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke the compiled model on a unique thread context
        result = app.invoke(email_payload, config)

        # Handle Pause/Interrupt workflow if required
        if "__interrupt__" in result:
            interrupt_info = result["__interrupt__"][-1].value
            print(f"\n--- INTERRUPT DETECTED ---")
            print(interrupt_info)

            # Simulate human intervention (accepting draft)
            action = input("Type 'yes' to approve draft, or 'no' to abort: ")
            approved = action.strip().lower() == "yes"

            # Resume execution
            resume_cmd = Command(
                resume={"approved": approved, "edited_response": None}
            )
            app.invoke(resume_cmd, config)
