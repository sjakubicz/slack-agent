from collections.abc import Callable

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from slack_agent.checking import Checker, CheckNode
from slack_agent.config import Config
from slack_agent.result import AgentResult
from slack_agent.utils import ensure_model


class Agent:
    def __init__(
        self,
        config: Config,
        tools: list[BaseTool],
        checker: Checker | None = None,
    ):
        ensure_model(config.model)
        self.tools = tools
        self.check = CheckNode(config, checker)
        self.model = ChatOllama(
            model=config.model,
            temperature=config.temperature,
            reasoning=config.reasoning,
        ).bind_tools(tools)
        self.graph = self.build()

    def model_node(self, state: MessagesState):
        return {'messages': [self.model.invoke(state['messages'])]}

    def build(self):
        builder = StateGraph(MessagesState)
        builder.add_node('model', self.model_node)
        builder.add_node('tools', ToolNode(self.tools))
        builder.add_node('check', self.check)
        builder.add_edge(START, 'model')
        builder.add_conditional_edges('model', tools_condition)
        builder.add_edge('tools', 'check')
        builder.add_conditional_edges('check', self.check.route)
        return builder.compile()

    def run(
        self, content: str, on_tool_call: Callable[[str], None]
    ) -> AgentResult:
        state: MessagesState = {'messages': [HumanMessage(content=content)]}
        result = AgentResult()
        for chunk in self.graph.stream(state, stream_mode='updates'):
            for update in chunk.values():
                result.add((update or {}).get('messages', []), on_tool_call)
        return result
