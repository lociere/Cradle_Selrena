# 该文件已格式化，内部备注/注释请使用中文说明
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

# 本模块定义了用于聊天消息负载的多模态“内容块”模型。
# 它与负载模式相互独立，便于其他代码直接导入使用这些类型。


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(..., description="text content string")


class ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: dict[str, str] = Field(
        ...,
        description="{'url': 'http://...' or 'data:image/...', 'detail': 'auto'}",
    )


class AudioContent(BaseModel):
    type: Literal["audio_url"] = "audio_url"
    audio_url: dict[str, str] = Field(
        ..., description="{'url': 'file://...' or 'http://...'}"
    )


class VideoContent(BaseModel):
    type: Literal["video_url"] = "video_url"
    video_url: dict[str, str] = Field(
        ..., description="{'url': 'file://...' or 'http://...'}"
    )


ContentBlock = Union[TextContent, ImageContent, AudioContent, VideoContent]
