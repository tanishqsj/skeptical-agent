import operator
from typing import Annotated, List, TypedDict, Union
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # The conversation history
    messages: Annotated[List[BaseMessage], operator.add]
    # Who sent the last message? (Manager, Coder, Skeptic)
    sender: str