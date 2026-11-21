from typing import NotRequired, TypedDict, cast

from langchain_core.messages import AnyMessage
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slack_agent.claims import check_claims, last_post, user_request
from slack_agent.config import Config
from slack_agent.dataset import Reviews


class SlackMessage(TypedDict):
    ts: str
    text: NotRequired[str]


class PostChecker:
    def __init__(self, config: Config, reviews: Reviews, client: WebClient):
        self.config = config
        self.reviews = reviews
        self.client = client

    def find_sent(self, channel: str, text: str) -> str | None:
        history = self.client.conversations_history(
            channel=channel, limit=self.config.slack.history_limit
        )
        messages = cast(list[SlackMessage], history['messages'] or [])
        return next(
            (m['ts'] for m in messages if m.get('text', '').strip() == text),
            None,
        )

    def __call__(self, messages: list[AnyMessage]) -> str | None:
        post = last_post(messages)
        if post is None:
            return None
        channel, text = str(post['channel']), str(post['text']).strip()
        markers = self.config.markers
        checks = self.config.checks

        try:
            sent_ts = self.find_sent(channel, text)
        except SlackApiError as e:
            error = checks.slack_error.format(error=e.response['error'])
            return f'{markers.failed} {error}'
        if sent_ts is None:
            return f'{markers.failed} {checks.not_in_channel}'

        request = user_request(messages)
        problem = check_claims(checks, self.reviews, messages, text, request)
        if problem is None:
            return f'{markers.passed} {checks.passed}'
        self.client.chat_delete(channel=channel, ts=sent_ts)
        return f'{markers.failed} {checks.deleted.format(problem=problem)}'
