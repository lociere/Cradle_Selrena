from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class TextContent(BaseModel):
    """
    纯文本内容块 (Text Schema)。
    
    用于表示消息中的文字部分。这是最基础的多模态单元。
    在构建 `PerceptionPayload`（内部/外部）时，通常作为 content 列表的一项。
    
    Attributes:
        type (Literal["text"]): 内容类型标识，固定为 "text"。
        text (str): 实际的文本字符串内容。
    """
    type: Literal["text"] = "text"
    text: str = Field(..., description="文本内容字符串")


class ImageContent(BaseModel):
    """
    图片内容块 (Image Schema)。
    
    用于表示消息中的图像部分。遵循 OpenAI GPT-4 VisionAPI 的标准格式。
    支持 HTTP URL 或 Base64 编码的数据 URI。
    
    Attributes:
        type (Literal["image_url"]): 内容类型标识，固定为 "image_url"。
        image_url (dict[str, str]): 包含图片信息的字典，通常包含 'url' 和可选的 'detail' 字段。
            - url: 图片地址 (http://...) 或 Base64 (data:image/...)。
            - detail: 图片细节级别 ('low', 'high', 'auto')。
    """
    type: Literal["image_url"] = "image_url"
    image_url: dict[str, str] = Field(
        ...,
        description="标准 OpenAI 图像格式: {'url': 'http://...' or 'data:image/...', 'detail': 'auto'}"
    )


class AudioContent(BaseModel):
    """
    音频内容块 (Audio Schema)。
    
    用于表示消息中的语音/音频部分。这是对标准 LLM 接口的扩展定义，
    用于支持多模态输入（如语音消息）。
    
    Attributes:
        type (Literal["audio_url"]): 内容类型标识，固定为 "audio_url"。
        audio_url (dict[str, str]): 包含音频信息的字典。
            - url: 音频文件地址或 Base64 编码。
    """
    type: Literal["audio_url"] = "audio_url"
    audio_url: dict[str, str] = Field(
        ...,
        description="音频资源格式: {'url': 'file://...' or 'http://...'}"
    )


class VideoContent(BaseModel):
    """
    视频内容块 (Video Schema)。
    
    用于表示消息中的视频部分。这是对标准 LLM 接口的扩展定义，
    通常用于视频流输入或视频文件分析。
    
    Attributes:
        type (Literal["video_url"]): 内容类型标识，固定为 "video_url"。
        video_url (dict[str, str]): 包含视频信息的字典。
            - url: 视频文件地址。
    """
    type: Literal["video_url"] = "video_url"
    video_url: dict[str, str] = Field(
        ...,
        description="视频资源格式: {'url': 'file://...' or 'http://...'}"
    )


# 联合类型：多模态内容块
# 在类型注解中推荐使用 ContentBlock 而非具体的类，以便于 Pydantic 自动解析多态。
ContentBlock = Union[TextContent, ImageContent, AudioContent, VideoContent]
