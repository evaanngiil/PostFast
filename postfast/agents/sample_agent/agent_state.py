from typing_extensions import TypedDict
from langgraph.graph import MessagesState

class InputState(MessagesState):
    pass

class InternalState(TypedDict):
    pass

class OutputState(TypedDict):
    output: str

class AgentState(InputState, InternalState, OutputState):
    pass