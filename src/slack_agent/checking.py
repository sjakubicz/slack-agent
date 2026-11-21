from collections.abc import Callable

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END, MessagesState

from slack_agent.config import Config

Checker = Callable[[list[AnyMessage]], str | None]


class CheckNode:
    def __init__(self, config: Config, checker: Checker | None):
        self.config = config
        self.checker = checker

    def __call__(self, state: MessagesState):
        messages = state['messages']
        feedback = self.checker(messages) if self.checker else None
        if feedback is None:
            return {'messages': []}

        failed = self.config.markers.failed
        failures = 1 + sum(
            isinstance(m, HumanMessage) and str(m.content).startswith(failed)
            for m in messages
        )
        reply: list[AnyMessage] = [HumanMessage(content=feedback)]
        if (
            feedback.startswith(failed)
            and failures >= self.config.max_failed_checks
        ):
            giving_up = self.config.messages.giving_up.format(failures=failures)
            reply.append(AIMessage(content=giving_up))
        return {'messages': reply}

    def route(self, state: MessagesState) -> str:
        return END if isinstance(state['messages'][-1], AIMessage) else 'model'
