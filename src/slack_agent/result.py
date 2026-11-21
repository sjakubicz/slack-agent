from collections.abc import Callable

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel

from slack_agent.utils import message_text


class AgentResult(BaseModel):
    answer: str = ''
    steps: list[str] = []
    checks: list[str] = []

    def add(
        self, messages: list[AnyMessage], on_tool_call: Callable[[str], None]
    ) -> None:
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    self.steps.append(f'`{call["name"]}({call["args"]})`')
                    on_tool_call(call['name'])
                if not message.tool_calls:
                    self.answer = message_text(message)
            elif isinstance(message, HumanMessage):
                self.checks.append(message_text(message))
