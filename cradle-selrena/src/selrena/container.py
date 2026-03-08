"""AI ???? - ????????"""

from pathlib import Path
from typing import Optional

from selrena.adapters import KernelAdapter, MemoryAdapter, PersonaAdapter
from selrena.application import ConversationService, MemoryService, ReasoningService
from selrena.domain.persona import Persona
from selrena.inference.llm import LLMBackend, DummyLLM, OpenAILLM, LocalLLM
from selrena.ports import KernelPort, MemoryPort, Personaport
from selrena.utils.logger import logger


class AIContainer:
    """
    AI ????
    
    ???
    1. ???????
    2. ??????
    3. ????????
    4. ??????
    """
    
    def __init__(self, config_dir: Path, data_dir: Path):
        self.config_dir = config_dir
        self.data_dir = data_dir
        
        # ???????????
        self.llm: Optional[LLMBackend] = None
        self.kernel: Optional[KernelPort] = None
        self.memory: Optional[MemoryPort] = None
        self.persona_adapter: Optional[Personaport] = None
        
        # ??????????
        self.conversation: Optional[ConversationService] = None
        self.memory_service: Optional[MemoryService] = None
        self.reasoning: Optional[ReasoningService] = None
        
        # ????
        self.current_persona: Optional[Persona] = None
        
        logger.info("AIContainer ?????")
    
    async def initialize(self, llm_config: dict, use_local_llm: bool = False):
        """
        ??????????
        
        Args:
            llm_config: LLM ????
            use_local_llm: ????????
        """
        logger.info("????? AI ??...")
        
        # 1. ??????
        self.kernel = KernelAdapter()
        self.memory = MemoryAdapter(self.data_dir / "memory")
        self.persona_adapter = PersonaAdapter(self.config_dir / "persona")
        
        # 2. 加载或创建 LLM
        if use_local_llm:
            model_path = llm_config.get("model_path", "")
            if not model_path:
                raise ValueError("需要指定本地模型路径")
            self.llm = LocalLLM(model_path)
            await self.llm.initialize()
        else:
            api_key = llm_config.get("api_key", "")
            if api_key:
                self.llm = OpenAILLM(
                    api_key=api_key,
                    base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
                    model=llm_config.get("model", "gpt-3.5-turbo"),
                )
            else:
                # 没有提供 API key 时使用 DummyLLM 以便本地测试
                logger.warning("未提供 LLM API key，使用 DummyLLM 模拟回复")
                self.llm = DummyLLM()
        
        # 3. ??????
        persona_name = llm_config.get("persona", "default")
        try:
            self.current_persona = await self.persona_adapter.load_persona(persona_name)
            logger.info(f"??????{persona_name}")
        except FileNotFoundError:
            logger.warning(f"???????????????{persona_name}")
            self.current_persona = Persona(
                name=persona_name,
                identity="???????????",
                values=["????", "????"],
                expression_style={"tone": "??"},
            )
        
        # 4. ?????
        self.memory_service = MemoryService(self.memory)
        self.conversation = ConversationService(
            persona=self.current_persona,
            llm=self.llm,
            kernel=self.kernel,
            memory=self.memory,
        )
        self.reasoning = ReasoningService(llm=self.llm)
        
        logger.info("AI ??????? ?")

    # accessors for external callers
    def get_conversation_service(self):
        if not self.conversation:
            raise RuntimeError("ConversationService not initialized")
        return self.conversation

    def get_memory_service(self):
        if not self.memory_service:
            raise RuntimeError("MemoryService not initialized")
        return self.memory_service

    def get_reasoning_service(self):
        if not self.reasoning:
            raise RuntimeError("ReasoningService not initialized")
        return self.reasoning

    def get_persona(self):
        return self.current_persona
    
    async def chat(self, message: str) -> str:
        """
        ? AI ???????
        
        Args:
            message: ????
            
        Returns:
            AI ??
        """
        if not self.conversation:
            raise RuntimeError("AI ??????")
        
        return await self.conversation.process_message(message)
    
    async def cleanup(self):
        """????"""
        logger.info("???? AI ????...")
        
        if self.llm:
            await self.llm.cleanup()
        
        logger.info("AI ????? ?")


# ??????
global_ai_container: Optional[AIContainer] = None


def get_container() -> AIContainer:
    """????????"""
    if global_ai_container is None:
        raise RuntimeError("AI ??????")
    return global_ai_container
