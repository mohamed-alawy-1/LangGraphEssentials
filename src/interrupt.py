import operator
from typing import Annotated, Literal, TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


# Define the state structure.
# Using Annotated with operator.add enables appending string lists together.
class State(TypedDict):
    nlist: Annotated[list[str], operator.add]


# Node A dynamically routes next steps based on user input.
# It uses the `interrupt()` helper function to pause graph execution and prompt
# for human interaction (admin review/input) when an unexpected input value is encountered.
def node_a(state: State) -> Command[Literal["b", "c", "d", END]]:
    print("Entered 'a' node")
    select = state["nlist"][-1]

    if select == "b":
        goto = "b"
    elif select == "c":
        goto = "c"
    elif select == "d":
        goto = "d"
    else:
        # Pause execution using LangGraph interrupt.
        # This raises an interrupt exception up to the caller and exposes the value.
        # The execution resumes from this exact line once the user feeds a response via a resume Command.
        admin = interrupt(f"Unexpected input '{select}'")
        print(f"Received human input from interrupt: {admin}")

        if admin == "continue":
            goto = "b"
        else:
            goto = END
            select = "q"

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

    # Compile the graph builder with the checkpointer to persist thread history and catch interrupts
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    # Create thread persistence checkpoint database simulation
    memory = InMemorySaver()

    # Define unique configuration specification for conversation session routing
    config = {"configurable": {"thread_id": "2"}}
    graph = build_graph(checkpointer=memory)

    while True:
        user = input("b, c, d, or q to quit: ")
        result = graph.invoke(State(nlist=[user]), config)
        print(result)

        # Check if the graph execution got paused/interrupted
        if "__interrupt__" in result:
            print(f"Interrupt context metadata: {result}")
            msg = result["__interrupt__"][-1].value
            human_input = input(f"\n[INTERRUPTED] {msg} -> Resolve by typing 'continue' or something else: ")

            # Construct resume Command payload to resume graph execution
            resume_command = Command(resume=human_input)
            result = graph.invoke(resume_command, config)
            print(result)

        if result["nlist"][-1] == "q":
            print("quit")
            break
