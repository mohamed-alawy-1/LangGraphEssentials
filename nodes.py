from typing import TypedDict
from langgraph.graph import END, START, StateGraph


class State(TypedDict): 
    name: str


def hello_node(state: State) -> State:
    print(f"Hello, {state['name']}!")
    return state


def build_graph() -> StateGraph:
    builder = StateGraph(State)
    builder.add_node("hello", hello_node)
    builder.add_edge(START, "hello")
    builder.add_edge("hello", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    graph.invoke(State(name="Mohamed"))
