import operator
from pydantic import BaseModel , Field
from typing import List
from typing import Literal , Union

class TranscriptionSegment(BaseModel):
    text: str = Field(..., description="The spoken words in this segment of the podcast.")
    duration: float = Field(..., description="How long the segment lasts in seconds.")
    offset: float = Field(..., description="When the segment begins in the full audio, in seconds.")
    lang: Literal["en" , "hi"] = Field(..., description='Language of the spoken text (only "en" or "hi" is expected).')
    
class Podcast(BaseModel):
    podcast_title :str =  Field(description="Name of the podcast")
    podcast_description: str = Field(description="Description of the podcast")
    transcript:List[TranscriptionSegment] = Field(description="List of the transcrption segments")
    video_id:str = Field(description="Video Id of the youtube video ie the podcast")


class Moment(BaseModel):
    reason:str = Field(description="Why this moment is compelling or viral-worthy in one line")
    start_time:str = Field(description="Start time of the clip from srt in srt format ex `00:21:43,039`")
    end_time:str = Field(description="End time of the clip from srt in srt format ex `00:21:43,039`")
    title:str = Field(description="Suitable Title for the short clip to make it viral")
    description:str = Field(description="2-3 lines description accordingly")
    keywords:List[str] = Field(description="some keywords suitable for the YT Shorts , TikToke and Instagram reels for the clip")

class Best_Podcast(BaseModel):
    video_id:str = Field(description = "Video Id of the best selected podcast")
    language:Literal['en' , 'hi'] = Field(description="Languages to fetch transcript en or hi")
    selected:bool = Field(description="If best podcast selected True if not False")

class MomentsList(BaseModel):
    Moments: List[Moment]