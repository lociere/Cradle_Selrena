"""
文件名称：multimodal_router.py
所属层级：推理层
核心作用：多模态输入编排与语义转述，不做业务流程和平台协议处理
"""
from dataclasses import dataclass
from typing import Any

from selrena.core.observability.logger import get_logger

logger = get_logger("multimodal_router")


@dataclass
class MultimodalRouteResult:
    """多模态路由输出：统一输入拆分为主文本与多模态语义文本。"""
    strategy: str
    primary_text: str
    semantic_text: str


class MultimodalRouter:
    """多模态双路径路由器。

    - core_direct: 直接把多模态项拼成核心多模态模型输入提示
    - specialist_then_core: 先由模态专有模型生成语义，再汇总给核心思考模型
    - 策略仅来自静态配置，不支持动态切换
    """

    def __init__(self, inference_config: Any):
        self._config = inference_config

    def route(self, model_input: dict | None) -> MultimodalRouteResult:
        if not model_input:
            return MultimodalRouteResult(
                strategy=self._config.multimodal.strategy,
                primary_text="",
                semantic_text="",
            )

        mm_config = self._config.multimodal
        items = self._normalize_items(model_input)
        primary_text = self._extract_primary_text(items)

        if not items:
            return MultimodalRouteResult(
                strategy=mm_config.strategy,
                primary_text=primary_text,
                semantic_text="",
            )

        if not mm_config.enabled:
            semantic_text = self._build_disabled_semantic(items)
            return MultimodalRouteResult(
                strategy=mm_config.strategy,
                primary_text=primary_text,
                semantic_text=semantic_text,
            )

        strategy = mm_config.strategy

        if strategy == "core_direct":
            semantic_text = self._build_core_direct_prompt(items)
            logger.debug("多模态路由完成", strategy=strategy, item_count=len(items))
            return MultimodalRouteResult(strategy=strategy, primary_text=primary_text, semantic_text=semantic_text)

        semantic_text = self._build_specialist_then_core_prompt(items)
        logger.debug("多模态路由完成", strategy="specialist_then_core", item_count=len(items))
        return MultimodalRouteResult(strategy="specialist_then_core", primary_text=primary_text, semantic_text=semantic_text)

    def _normalize_items(self, model_input: dict) -> list[dict]:
        raw_items = list(model_input.get("items", []))
        return raw_items[: self._config.multimodal.max_items]

    def _extract_primary_text(self, items: list[dict]) -> str:
        text_parts: list[str] = []
        for item in items:
            if str(item.get("modality", "")) != "text":
                continue
            text = str(item.get("text", "")).strip()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts).strip()

    def _build_disabled_semantic(self, items: list[dict]) -> str:
        lines = ["[多模态处理已禁用] 非文本模态将降级为占位符："]
        for index, item in enumerate(items, start=1):
            modality = str(item.get("modality", "unknown"))
            if modality == "text":
                continue
            uri = str(item.get("uri", ""))
            lines.append(f"{index}. [{modality} 占位符] {uri or '无资源地址'}")
        return "\n".join(lines)

    def _build_core_direct_prompt(self, items: list[dict]) -> str:
        lines = [f"[多模态直连:{self._config.multimodal.core_model}] 请直接理解以下多模态输入："]
        for index, item in enumerate(items, start=1):
            modality = str(item.get("modality", "unknown"))
            text = str(item.get("text", ""))
            uri = str(item.get("uri", ""))
            hint = str(item.get("description_hint", ""))
            lines.append(f"{index}. modality={modality}, text={text}, uri={uri}, hint={hint}")
        return "\n".join(lines)

    def _build_specialist_then_core_prompt(self, items: list[dict]) -> str:
        lines = [f"[多模态专有模型预处理后汇总] 核心模型:{self._config.multimodal.core_model}"]
        for index, item in enumerate(items, start=1):
            modality = str(item.get("modality", "unknown"))
            if modality == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    lines.append(f"{index}. [文本输入] {text}")
                continue
            if modality == "image":
                summary = self._run_image_specialist(item)
            elif modality == "video":
                summary = self._run_video_specialist(item)
            else:
                summary = self._run_generic_specialist(item)
            lines.append(f"{index}. {summary}")
        return "\n".join(lines)

    def _run_image_specialist(self, item: dict) -> str:
        uri = str(item.get("uri", ""))
        hint = str(item.get("description_hint", ""))
        if not self._config.multimodal.image_model:
            return f"[图像占位符] {uri or '无资源地址'}"
        return f"[图像模型:{self._config.multimodal.image_model}] 对 {uri} 的语义摘要: {hint or '未提供提示，需自动描述主体/场景/文字信息'}"

    def _run_video_specialist(self, item: dict) -> str:
        uri = str(item.get("uri", ""))
        hint = str(item.get("description_hint", ""))
        if not self._config.multimodal.video_model:
            return f"[视频占位符] {uri or '无资源地址'}"
        return f"[视频模型:{self._config.multimodal.video_model}] 对 {uri} 的语义摘要: {hint or '未提供提示，需自动提取关键帧与事件'}"

    def _run_generic_specialist(self, item: dict) -> str:
        modality = str(item.get("modality", "unknown"))
        uri = str(item.get("uri", ""))
        return f"[通用专有模型] modality={modality}, uri={uri}, 语义摘要待补充"
