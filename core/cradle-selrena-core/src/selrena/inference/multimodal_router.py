"""
文件名称：multimodal_router.py
所属层级：推理层
核心作用：多模态输入编排与语义转述，不做业务流程和平台协议处理
"""
from dataclasses import dataclass
from typing import Iterable

from selrena.core.config import InferenceConfig
from selrena.core.contracts.kernel_ingress_contracts import PerceptionEventContentModel
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

    def __init__(self, inference_config: InferenceConfig):
        self._config = inference_config

    def route(self, model_input: PerceptionEventContentModel | dict | None) -> MultimodalRouteResult:
        if not model_input:
            return MultimodalRouteResult(
                strategy=self._config.multimodal.strategy,
                primary_text="",
                semantic_text="",
            )

        content = model_input if isinstance(model_input, PerceptionEventContentModel) else PerceptionEventContentModel.model_validate(model_input)
        primary_text = content.text or ""
        mm_config = self._config.multimodal

        has_non_text = any(m != "text" for m in content.modality)
        if not has_non_text:
            return MultimodalRouteResult(
                strategy=mm_config.strategy,
                primary_text=primary_text,
                semantic_text="",
            )

        if not mm_config.enabled:
            semantic_text = "[多模态处理已禁用] 非文本模态将降级。包含模态: " + ", ".join(content.modality)
            return MultimodalRouteResult(
                strategy=mm_config.strategy,
                primary_text=primary_text,
                semantic_text=semantic_text,
            )

        strategy = mm_config.strategy
        
        # 简化路由逻辑，基于新版内容模型
        if strategy == "core_direct":
            semantic_text = f"[多模态直连:{mm_config.core_model}] 输入模态: {', '.join(content.modality)}。附带原始数据: {content.raw}"
            logger.debug("多模态路由完成", strategy=strategy, modality=content.modality)
            return MultimodalRouteResult(strategy=strategy, primary_text=primary_text, semantic_text=semantic_text)
        
        semantic_text = f"[多模态专有模型汇总] 核心模型:{mm_config.core_model}。输入模态: {', '.join(content.modality)}。附带原始数据: {content.raw}"
        logger.debug("多模态路由完成", strategy="specialist_then_core", modality=content.modality)
        return MultimodalRouteResult(strategy="specialist_then_core", primary_text=primary_text, semantic_text=semantic_text)

    # 遗留的多模态解析辅助方法（因为结构变更暂时废弃或精简）
