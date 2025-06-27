from rag import RAGSystem
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from tools.rag_inputs import *

def re_full_text(results):
    retrieved_text = ""
    for i, result in enumerate(results, 1):
        retrieved_text += f"\nResult {i}:\n"
        retrieved_text += f"Text: {result['text']}\n"  # Note: removed the [:200] to get full text
        retrieved_text += f"Source: {result.get('source', 'Unknown')}\n"
        retrieved_text += f"Rerank Score: {result['rerank_score']}\n"


    # If you want just the concatenated text without metadata:
    just_text = "\n".join(result['text'] for result in results)
    return just_text

class FetchRAGAnswer(BaseTool):
    name: str = "fetch_rag_answers"
    description: str = "Get the answer for the given question"
    args_schema: Type[BaseModel] = QuestionInput

    def _run(
        self, question: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:

        try:
            rag = RAGSystem()
            results = rag.hybrid_search(question)
            print(re_full_text(results))
            return re_full_text(results)

        except:
            return "No answer found for the given question"

    async def _arun(
        self,
        question: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return self._run(question)