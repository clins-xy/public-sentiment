from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


SourceType = Literal["news", "image", "video", "forum_post", "internal_data"]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StrictStr = Field(min_length=1, max_length=200)
    source_types: list[SourceType] = Field(
        default_factory=lambda: ["news", "image", "video", "forum_post", "internal_data"], min_length=1,
    )

    @field_validator("query")
    @classmethod
    def nonempty_query(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("主题词不能为空")
        return value


class GraphQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: StrictStr = ""
    node: StrictStr = ""
    node_type: StrictStr = ""
    relation: StrictStr = ""


class ForumHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: StrictStr = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
