import operator
from typing import Annotated, Literal, TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


# Define the state structure.
# Using Annotated with operator.add enables appending string lists together.
class State(TypedDict):
    nlist: Annotated[list[str], operator.add]


# Node A controls the routing logic dynamically based on user input.
def node_a(state: State) -> Command[Literal["b", "c", "d", END]]:
    select = state["nlist"][-1]

    # Dynamic routing selector
    if select == "b":
        goto = "b"
    elif select == "c":
        goto = "c"
    elif select == "d":
        goto = "d"
    else:
        goto = END

    return Command(
        update=State(nlist=[select]),
        goto=[goto],
    )


# Standard nodes that update state variables and automatically move next
def node_b(state: State) -> State:
    return State(nlist=["B"])


def node_c(state: State) -> State:
    return State(nlist=["C"])


def node_d(state: State) -> State:
    return State(nlist=["D"])


# Construct the StateGraph incorporating a checkpoint saver to persist execution state history (memory).
def build_graph(checkpointer: InMemorySaver) -> StateGraph:
    builder = StateGraph(State)

    # Register nodes
    builder.add_node("a", node_a)
    builder.add_node("b", node_b)
    builder.add_node("c", node_c)
    builder.add_node("d", node_d)

    # Set up static edges
    builder.add_edge(START, "a")
    builder.add_edge("b", END)
    builder.add_edge("c", END)
    builder.add_edge("d", END)

    # Compile the graph with a checkpointer memory saver to enable persistence/history tracking
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # Create database simulator (in-memory persistence store)
    memory = InMemorySaver()

    # Define configuration structure specifying the thread_id.
    # Thread ID controls which conversational/interaction thread session memory checkpoint to access.
    config = {"configurable": {"thread_id": "1"}}
    graph = build_graph(checkpointer=memory)

    # Interactive loops to show State Persistence across invocations within the same thread_id context
    while True:
        user = input("b, c, d, or q to quit: ")
        result = graph.invoke(State(nlist=[user]), config)
        print(result)
        if result["nlist"][-1] == "q":
            print("quit")
            break