import operator
from typing import Annotated, List, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


# Define the state structure.
# Using Annotated with operator.add enables appending string lists together.
class State(TypedDict):
    nlist: Annotated[List[str], operator.add]


# Node A controls the routing logic dynamically.
# By returning a Command object, node_a can specify both the update to the state
# and dynamically decide the list of next nodes to navigate to (using 'goto').
def node_a(state: State) -> Command[Literal["b", "c", "d", END]]:
    select = state["nlist"][-1]

    # Dynamic routing based on the last input character
    if select == "b":
        goto = "b"
    elif select == "c":
        goto = "c"
    elif select == "d":
        goto = "d"
    else:
        goto = END  # Any other input (including 'q') sends the graph to END

    return Command(
        update=State(nlist=[select]),
        goto=[goto],
    )


# Standard nodes that update state variables and forward automatically to END
def node_b(state: State) -> State:
    return State(nlist=["B"])


def node_c(state: State) -> State:
    return State(nlist=["C"])


def node_d(state: State) -> State:
    return State(nlist=["D"])


# Construct the StateGraph showing dynamic (conditional) routing
def build_graph() -> StateGraph:
    builder = StateGraph(State)

    # Register all processing nodes
    builder.add_node("a", node_a)
    builder.add_node("b", node_b)
    builder.add_node("c", node_c)
    builder.add_node("d", node_d)

    # Establish static edges
    # START points to 'a', while 'b', 'c', and 'd' automatically transition to END
    builder.add_edge(START, "a")
    builder.add_edge("b", END)
    builder.add_edge("c", END)
    builder.add_edge("d", END)

    # Compiled pregel graph instance
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()

    # Interactive loops to demonstrate conditional routing
    while True:
        user = input("b, c, d, or q to quit: ")
        result = graph.invoke(State(nlist=[user]))
        print(result)
        if result["nlist"][-1] == "q":
            print("quit")
            break
