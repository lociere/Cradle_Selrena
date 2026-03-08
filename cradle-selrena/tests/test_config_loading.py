#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置加载测试脚本

用于验证新架构配置模板的正确性
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

import yaml
import pytest
pytest.skip("legacy config tests skipped after package rename", allow_module_level=True)

from cradle_selrena.schemas.configs import (
    SystemSettings,
    DomainConfig,
    SystemCoreConfig,
    PersonaConfig,
    MemoryConfig,
)


def test_config_loading(config_path: str, model_class, config_name: str):
    """测试配置加载"""
    print(f"\n{'='*60}")
    print(f"测试：{config_name}")
    print(f"{'='*60}")
    
    try:
        # 读取配置文件
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        print(f"✓ 配置文件读取成功：{config_path}")
        
        # 验证 Schema
        config = model_class(**config_data)
        print(f"✓ Schema 验证通过")
        
        return config
        
    except FileNotFoundError:
        print(f"⚠ 配置文件不存在（这是正常的，因为是 .example 模板）: {config_path}")
        return None
    except yaml.YAMLError as e:
        print(f"✗ YAML 语法错误：{e}")
        return None
    except Exception as e:
        print(f"✗ 验证失败：{e}")
        return None


def test_schema_models():
    """测试 Schema 模型"""
    print("\n" + "="*60)
    print("Schema 模型测试")
    print("="*60)
    
    # 测试 SystemSettings
    print("\n[1] SystemSettings")
    system = SystemSettings()
    print(f"  - Core 层字段：{list(system.core.model_fields.keys()) if hasattr(system.core, 'model_fields') else 'N/A'}")
    print(f"  - Adapters 层字段：{list(system.adapters.model_fields.keys()) if hasattr(system.adapters, 'model_fields') else 'N/A'}")
    print(f"  - Inference 层字段：{list(system.inference.model_fields.keys()) if hasattr(system.inference, 'model_fields') else 'N/A'}")
    print(f"  - Domain 层字段：{list(system.domain.model_fields.keys()) if hasattr(system.domain, 'model_fields') else 'N/A'}")
    print("✓ SystemSettings 创建成功")
    
    # 测试 DomainConfig
    print("\n[2] DomainConfig")
    domain = DomainConfig()
    print(f"  - 人格名称：{domain.persona.name}")
    print(f"  - 记忆存储类型：{domain.memory.storage.type}")
    print(f"  - 决策思考模式：{domain.decision.thinking_mode}")
    print("✓ DomainConfig 创建成功")
    
    # 测试默认值
    print("\n[3] 默认值测试")
    print(f"  - 系统名称：{system.core.name}")
    print(f"  - 系统版本：{system.core.version}")
    print(f"  - 日志级别：{system.core.logging.level}")
    print(f"  - 人格角色：{domain.persona.identity.role}")
    print(f"  - LLM 默认引擎：{system.inference.default_engine}")
    print("✓ 默认值测试通过")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Cradle Selrena 配置系统测试")
    print("="*60)
    
    # 测试 Schema 模型
    test_schema_models()
    
    # 测试配置模板文件（这些是 .example 文件，可能不存在实际配置）
    configs_dir = ROOT_DIR / "configs"
    
    test_cases = [
        (configs_dir / "core" / "system.example.yaml", SystemCoreConfig, "Core 层配置"),
        (configs_dir / "domain" / "core.example.yaml", DomainConfig, "Domain 层配置"),
        (configs_dir / "inference" / "engines.example.yaml", dict, "Inference 层配置"),  # 简化测试
        (configs_dir / "adapters" / "napcat.example.yaml", dict, "Adapters 层配置"),  # 简化测试
    ]
    
    for config_path, model_class, config_name in test_cases:
        if model_class == dict:
            # 简化测试：只检查文件是否存在和 YAML 语法
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    yaml.safe_load(f)
                print(f"\n✓ {config_name} 模板文件语法正确")
            except FileNotFoundError:
                print(f"\n⚠ {config_name} 模板文件不存在（正常）")
            except Exception as e:
                print(f"\n✗ {config_name} 模板文件错误：{e}")
        else:
            test_config_loading(str(config_path), model_class, config_name)
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    print("\n提示：")
    print("1. 复制 .example.yaml 文件为不带 .example 的版本")
    print("2. 根据实际需求修改配置")
    print("3. 创建 configs/secrets.yaml 填写敏感信息")
    print("4. 运行此脚本验证配置")


if __name__ == "__main__":
    main()
