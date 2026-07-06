from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# Define the state structure for the graph.
# The state is passed between nodes and holds the data that the graph operates on.
class State(TypedDict):
    name: str


# Define a node function.
# Nodes are python functions that take the current state and return an updated state.
def hello_node(state: State) -> State:
    print(f"Hello, {state['name']}!")
    return state


# Function to construct and compile the LangGraph workflow.
def build_graph() -> StateGraph:
    # Initialize the graph builder with the defined State schema.
    builder = StateGraph(State)

    # Register the nodes in the graph.
    builder.add_node("hello", hello_node)

    # Establish connections (edges) between nodes.
    # START is a special node indicating where the graph execution begins.
    builder.add_edge(START, "hello")
    # END is a special transition indicating where graph execution terminates.
    builder.add_edge("hello", END)

    # Compile the graph builder into an executable Pregel graph.
    return builder.compile()


if __name__ == "__main__":
    # Compile the graph
    graph = build_graph()

    # Run the graph with an initial payload
    graph.invoke(State(name="Mohamed"))
