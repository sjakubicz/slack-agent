from langchain_core.tools import BaseTool, tool
from slack_sdk import WebClient

from slack_agent.dataset import Reviews


def build_tools(reviews: Reviews, client: WebClient) -> list[BaseTool]:
    @tool
    def analyze_reviews(keyword: str) -> str:
        """Analyze movie reviews (Rotten Tomatoes dataset) that mention a word.
        Returns how many reviews mention it, the share that are positive, and
        example snippets. Use this for any question about movie reviews.
        """
        config = reviews.config
        count, positive = reviews.stats(keyword)
        if count == 0:
            return f'No reviews mention "{keyword}".'
        examples = ' | '.join(
            r[config.text_field][: config.example_length]
            for r in reviews.find(keyword)[: config.example_count]
        )
        return (
            f'{count} reviews mention "{keyword}"; {positive} are positive. '
            f'Examples: {examples}'
        )

    @tool
    def post_to_channel(channel: str, text: str) -> str:
        """Post a message to a Slack channel.
        `channel` must be a channel ID and the bot must be a member
        of it. Plain messages are posted exactly as the user asked. Before
        posting review statistics, run analyze_reviews on a word from the user
        request and copy its exact review count and positive percentage into
        the message.
        """
        sent = client.chat_postMessage(channel=channel, text=text)
        return f'Posted (ts={sent["ts"]}).'

    return [analyze_reviews, post_to_channel]
