from typing_extensions import TypedDict
from langgraph.graph import MessagesState

class InputState(MessagesState):
    pass

class InternalState(MessagesState):
    output: str

class OutputState(TypedDict):
    output: str

