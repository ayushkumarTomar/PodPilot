import operator
from typing import Annotated, TypedDict, Union , List , Optional , Any , Literal
from schema import TranscriptionSegment , Moment , Podcast
from langchain_core.agents import AgentAction, AgentFinish
class AgentState(TypedDict):
    input:str
    podcast:Optional[Podcast]
    Moments: Optional[Moment]
    agent_outcome: Union[AgentAction, AgentFinish, None]
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]
    podcast_list:Any
    retry:Literal[None , "week" , "month"]