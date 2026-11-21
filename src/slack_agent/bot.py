import logging
import re
from typing import Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from slack_agent.agent import Agent
from slack_agent.config import Config
from slack_agent.result import AgentResult
from slack_agent.utils import first_env, to_slack_markdown

logger = logging.getLogger(__name__)


class SlackBot:
    def __init__(self, config: Config, agent: Agent):
        self.texts = config.messages
        self.agent = agent
        self.app_token = first_env(config.slack.app_token_envs)
        self.app = App(token=first_env(config.slack.bot_token_envs))
        self.app.event('app_mention')(self.on_mention)
        self.app.event('message')(self.on_dm)

    def format_answer(self, result: AgentResult) -> str:
        texts = self.texts
        answer = to_slack_markdown(result.answer) or f'_{texts.no_response}_'
        if result.steps:
            answer += f'\n\n_{texts.tools_used}_ ' + ', '.join(result.steps)
        if result.checks:
            answer += f'\n_{texts.self_check}_ ' + result.checks[-1]
        return answer

    def respond(
        self, text: str, channel: str, thread_ts: str | None, client: WebClient
    ) -> None:
        placeholder = client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, text=self.texts.thinking
        )
        ts = str(placeholder['ts'])

        def on_tool_call(name: str) -> None:
            calling = self.texts.calling.format(tool=name)
            client.chat_update(channel=channel, ts=ts, text=calling)

        try:
            answer = self.format_answer(self.agent.run(text, on_tool_call))
        except Exception:
            logger.exception('Agent failed')
            answer = self.texts.error
        client.chat_update(channel=channel, ts=ts, text=answer)

    def on_mention(self, event: dict[str, Any], client: WebClient) -> None:
        text = re.sub(r'<@[A-Z0-9]+>', '', event['text']).strip()
        thread_ts = event.get('thread_ts') or event['ts']
        self.respond(text, event['channel'], thread_ts, client)

    def on_dm(self, event: dict[str, Any], client: WebClient) -> None:
        if (
            event.get('channel_type') != 'im'
            or event.get('bot_id')
            or event.get('subtype')
        ):
            return
        self.respond(event['text'], event['channel'], None, client)

    def start(self) -> None:
        SocketModeHandler(self.app, self.app_token).start()
