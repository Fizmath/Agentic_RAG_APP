from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from typing import  Literal
from langgraph.graph import MessagesState
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field


class GraphBuilder:
    def __init__(self, tools, llm_model: str = "qwen3:1.7b"):
        self.tools = tools
        self.llm_model = llm_model
        self.workflow = StateGraph(MessagesState)
        self._build_graph()

    def generate_query_or_respond(self , state: MessagesState):
        """Call the model to generate a response based on the current state. Given
        the question, it will decide to retrieve using the retriever tool, or simply respond to the user.
        """
        response = (
            ChatOllama(temperature=0, model=self.llm_model)
            .bind_tools([self.tools]).invoke(state["messages"])  
        )
        return {"messages": [response]}
    
    def grade_documents(self, state) ->  Literal["generate_answer", "rewrite_question"]:
            """Determine whether the retrieved documents are relevant to the question."""

            print("---CHECK RELEVANCE---")
            class GradeDocuments(BaseModel):  
                """Grade documents using a binary score for relevance check."""
                binary_score: str = Field(
                    description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
                )

            question = state["messages"][0].content
            context = state["messages"][-1].content

            grader_model = ChatOllama(temperature=0, model=self.llm_model)

            GRADE_PROMPT = (
                    "You are a grader assessing relevance of a retrieved document to a user question. \n "
                    "Here is the retrieved document: \n\n {context} \n\n"
                    "Here is the user question: {question} \n"
                    "If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n"
                    "Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."
                )

            prompt = GRADE_PROMPT.format(question=question, context=context)

            response = (
                grader_model
                .with_structured_output(GradeDocuments).invoke(  
                    [{"role": "user", "content": prompt}]
                )
            )
            score = response.binary_score


            if score == "yes":
                print("---DECISION: DOCS RELEVANT---")
                return "generate_answer"

            else:
                print("---DECISION: DOCS NOT RELEVANT---")
                return "rewrite_question"
            
    def rewrite_question(self, state: MessagesState):
        """Rewrite the original user question."""
        REWRITE_PROMPT = (
            "Look at the input and try to reason about the underlying semantic intent / meaning.\n"
            "Here is the initial question:"
            "\n ------- \n"
            "{question}"
            "\n ------- \n"
            "Formulate an improved question:"
        )
        messages = state["messages"]
        question = messages[0].content
        prompt = REWRITE_PROMPT.format(question=question)
        response_model = ChatOllama(temperature=0, model=self.llm_model)
        response = response_model.invoke([{"role": "user", "content": prompt}])
        return {"messages": [{"role": "user", "content": response.content}]}   

    def generate_answer(self, state: MessagesState):
        """Generate an answer."""
        GENERATE_PROMPT = (
            "You are an assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer, just say that you don't know. "
            "Use three sentences maximum and keep the answer concise.\n"
            "Question: {question} \n"
            "Context: {context}"
        )
        question = state["messages"][0].content
        context = state["messages"][-1].content
        prompt = GENERATE_PROMPT.format(question=question, context=context)
        response_model = ChatOllama(temperature=0, model=self.llm_model)
        response = response_model.invoke([{"role": "user", "content": prompt}])
        return {"messages": [response]} 

    def _build_graph(self):
        self.workflow.add_node(self.generate_query_or_respond)
        self.workflow.add_node("retrieve", ToolNode([self.tools]))
        self.workflow.add_node(self.rewrite_question)
        self.workflow.add_node(self.generate_answer)

        self.workflow.add_edge(START, "generate_query_or_respond")

        # Decide whether to retrieve
        self.workflow.add_conditional_edges(
            "generate_query_or_respond",
            # Assess LLM decision (call `retriever_tool` tool or respond to the user)
            tools_condition,
            {
                # Translate the condition outputs to nodes in our graph
                "tools": "retrieve",
                END: END,
            },
        )
        # Edges taken after the `action` node is called.
        self.workflow.add_conditional_edges(
            "retrieve",
            # Assess agent decision
            self.grade_documents,
        )
        self.workflow.add_edge("generate_answer", END)
        self.workflow.add_edge("rewrite_question", "generate_query_or_respond")

    def compile(self):
        return self.workflow.compile()