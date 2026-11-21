from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Section(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DatasetConfig(Section):
    name: str
    split: str
    text_field: str
    label_field: str
    example_count: int = Field(ge=0)
    example_length: int = Field(ge=1)


class SlackConfig(Section):
    bot_token_envs: list[str] = Field(min_length=1)
    app_token_envs: list[str] = Field(min_length=1)
    history_limit: int = Field(ge=1)


class MessagesConfig(Section):
    thinking: str
    calling: str
    no_response: str
    error: str
    tools_used: str
    self_check: str
    giving_up: str

    @model_validator(mode='after')
    def calling_names_the_tool(self):
        if '{tool}' not in self.calling:
            raise ValueError('messages.calling must contain {tool}')
        return self


class ChecksConfig(Section):
    passed: str
    slack_error: str
    not_in_channel: str
    deleted: str
    hint: str
    keyword_not_in_request: str
    no_matches: str
    keyword_not_mentioned: str
    missing_positive: str
    wrong_percent: str
    missing_count: str
    unsourced_statistics: str


class MarkersConfig(Section):
    passed: str = Field(min_length=1)
    failed: str = Field(min_length=1)

    @model_validator(mode='after')
    def markers_differ(self):
        if self.passed == self.failed:
            raise ValueError('markers.passed and markers.failed must differ')
        return self


class Config(Section):
    model: str
    temperature: float = Field(ge=0)
    reasoning: bool
    max_failed_checks: int = Field(ge=1)
    dataset: DatasetConfig
    slack: SlackConfig
    messages: MessagesConfig
    checks: ChecksConfig
    markers: MarkersConfig

    @classmethod
    def load(cls, path: Path):
        return cls.model_validate_json(path.read_text())
