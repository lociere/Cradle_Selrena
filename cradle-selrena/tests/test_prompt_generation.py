#!/usr/bin/env python
"""测试提示词生成系统"""

import pytest
pytest.skip("legacy prompt tests skipped after package rename", allow_module_level=True)

from cradle_selrena.schemas.configs import DomainConfig
from cradle_selrena.configs.prompts import PromptManager, PromptContext

def test_prompt_generation():
    """测试提示词生成"""
    print("=" * 60)
    print("Cradle Selrena 提示词生成系统测试")
    print("=" * 60)
    
    # 创建配置
    config = DomainConfig()
    print(f"✓ DomainConfig 创建成功")
    print(f"  - 人格名称：{config.persona.name}")
    print(f"  - 人格版本：{config.persona.version}")
    print(f"  - 角色：{config.persona.identity.role}")
    print(f"  - 提示词模板：{config.persona.prompt_template}")
    
    # 创建提示词管理器
    manager = PromptManager()
    print(f"✓ PromptManager 初始化成功")
    
    # 测试加载静态提示词
    print("\n1. 测试加载静态提示词...")
    prompt_content = manager.load_prompt("system_prompt")
    print(f"✓ 加载成功，长度：{len(prompt_content)} 字符")
    
    # 测试渲染模板
    print("\n2. 测试渲染提示词模板...")
    context = PromptContext(
        persona_name=config.persona.name,
        persona_role=config.persona.identity.role,
        memory_summary="用户最近对 AI 技术很感兴趣",
        user_profile="用户名：测试用户"
    )
    rendered = manager.render_prompt("system_prompt", context=context)
    print(f"✓ 渲染成功，长度：{len(rendered)} 字符")
    
    # 测试获取系统提示词
    print("\n3. 测试获取系统提示词...")
    persona_config = {
        "name": config.persona.name,
        "identity": {
            "role": config.persona.identity.role
        }
    }
    system_prompt = manager.get_system_prompt(
        persona_config=persona_config,
        memory_summary="用户询问了关于提示词管理的问题",
        user_profile="活跃用户"
    )
    print(f"✓ 生成成功，长度：{len(system_prompt)} 字符")
    
    # 显示提示词预览
    print("\n" + "=" * 60)
    print("系统提示词预览（前 500 字符）:")
    print("=" * 60)
    print(system_prompt[:500])
    print("...")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_prompt_generation()
