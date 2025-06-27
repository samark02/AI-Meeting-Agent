from typing import Type
from pydantic import BaseModel, Field, create_model

class QuestionInput(BaseModel):
    question: str = Field(description="Question from the user (Question should match any one of the available questions.)")

class QuestionInputCards(BaseModel):
    question: str = Field(description="")
    
    @classmethod
    def with_description(cls, description: str) -> Type[BaseModel]:
        return create_model(
            cls.__name__,
            question=(str, Field(default=cls.__annotations__['question'], description=description))
        )
