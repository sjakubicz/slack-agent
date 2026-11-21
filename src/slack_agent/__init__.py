import logging
from pathlib import Path

from dotenv import load_dotenv
from slack_sdk import WebClient

from slack_agent.agent import Agent
from slack_agent.bot import SlackBot
from slack_agent.config import Config
from slack_agent.dataset import Reviews
from slack_agent.tools import build_tools
from slack_agent.utils import first_env
from slack_agent.verify import PostChecker


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    config = Config.load(path=Path(__file__).with_name('config.json'))
    reviews = Reviews(config.dataset)
    slack = WebClient(token=first_env(config.slack.bot_token_envs))
    agent = Agent(
        config=config,
        tools=build_tools(reviews, slack),
        checker=PostChecker(config, reviews, slack),
    )
    SlackBot(config, agent).start()
