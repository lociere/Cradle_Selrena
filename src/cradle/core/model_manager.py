import os
import shutil
from pathlib import Path
from typing import Optional
from cradle.utils.path import ProjectPath
from cradle.utils.logger import logger

class ModelManager:
    """
    统一模型资源管理器 (Unified Model Asset Manager)
    
    核心职责:
    1. 作为一个 '安装器'，自动将云端模型固化到 assets/models 目录
    2. 作为一个 '沙盒'，拦截并重定向第三方库的临时缓存
    3. 作为一个 '解析器'，为上层应用提供统一的模型绝对路径
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logger
        # 定义沙盒路径 (仅用于捕获库产生的临时文件，不再作为主要存储)
        self.hub_cache_sandbox = ProjectPath.DATA_CACHE / "hub_sandbox"
        
        # 注入环境变量 (构建防污染围栏)
        self._setup_sandbox()
        
        self._initialized = True

    def _setup_sandbox(self):
        """
        设置环境变量充当 '沙盒'
        防止第三方库(ModelScope/HuggingFace)将临时索引或锁文件写入 C 盘用户目录
        """
        sandbox = str(self.hub_cache_sandbox)
        # 强制接管主流 AI 库的缓存路径
        os.environ["MODELSCOPE_CACHE"] = sandbox
        os.environ["HF_HOME"] = sandbox
        os.environ["TORCH_HOME"] = sandbox
        os.environ["XDG_CACHE_HOME"] = sandbox # Linux/通用 Fallback
        
    def resolve_model_path(self, model_identifier: str, auto_download: bool = True) -> str:
        """
        解析模型路径。遵循 "本地优先 -> 自动安装" 策略。
        
        :param model_identifier: 模型ID (如 'iic/SenseVoiceSmall') 或 本地文件名
        :param auto_download: 如果本地不存在，是否允许尝试自动下载
        :return: 可供加载的绝对路径
        """
        # 1. 绝对路径检查 (用户可能手动指定了绝对路径)
        if os.path.isabs(model_identifier):
            path_obj = Path(model_identifier)
            if path_obj.exists():
                return str(path_obj.resolve())
            self.logger.warning(f"Configured absolute path not found: {model_identifier}")

        # 2. 构造标准的静态资源路径
        # 规则: 提取 ID 的最后一部分作为本地目录名
        # e.g., 'iic/SenseVoiceSmall' -> 'assets/models/SenseVoiceSmall'
        model_name_clean = model_identifier.split("/")[-1]
        local_asset_path = ProjectPath.ASSETS_MODELS / model_name_clean
        
        # 3. 本地命中检查
        # 检查是否已经存在并且完整
        if local_asset_path.exists():
            if self._validate_integrity(local_asset_path):
                self.logger.info(f"Using verified local asset: {local_asset_path}")
                return str(local_asset_path.resolve())
            else:
                self.logger.warning(f"Model integrity check failed for {local_asset_path}. Re-installing...")
                # 能够走到这里说明存在但无效 (无法补救)，强制清理以便重新下载
                if local_asset_path.is_dir():
                    shutil.rmtree(local_asset_path, ignore_errors=True)
                else:
                    local_asset_path.unlink(missing_ok=True)

        # 4. 自动安装流程
        if auto_download:
            try:
                return self._install_from_hub(model_identifier, local_asset_path)
            except Exception:
                # 安装失败时，如果是单纯的网络问题，或许可以让上层库自己重试，或者直接抛出异常
                # 这里我们选择向上传递异常，确保启动流程感知到错误
                raise

        # 5. 最后的兜底 (返回原始 ID，听天由命)
        return model_identifier
    
    def _validate_integrity(self, model_path: Path) -> bool:
        """
        验证模型目录完整性
        
        策略:
        1. [Fast Path] 检查 .complete 标记文件 (极速验证)
        2. [Deep Scan] 如果无标记，检查核心权重文件，如果有效则自动补充标记 (兼容旧版本/迁移)
        3. [Cleanup] 清理临时残留 (.______temp)
        """
        if not model_path.exists():
            return False
            
        # 如果是单文件而非目录，只需非空即可
        if model_path.is_file():
            return model_path.stat().st_size > 0

        if not model_path.is_dir():
            return False
            
        # 1. 检查完成标记 (最快路径)
        if (model_path / ".complete").exists():
            return True

        # 2. 深度扫描: 寻找核心权重文件
        # 定义可能的权重文件后缀
        weight_suffixes = {'.pt', '.bin', '.safetensors', '.onnx', '.engine', '.model'}
        valid_weights_found = False
        
        try:
            # 遍历一级目录 (通常权重在根目录)
            # 兼容性: 某些情况下(git clone), 可能会有多级目录，但通常 Snapshot Download 都在根下
            for file in model_path.iterdir():
                if file.is_file() and file.suffix in weight_suffixes:
                    # 宽松检查: > 10MB 即视为有效权重 (避免只是个占位符)
                    if file.stat().st_size > 10 * 1024 * 1024: 
                        valid_weights_found = True
                        break
        except Exception:
            pass # 权限问题等
            
        # 3. 结果判定与自动维护
        if valid_weights_found:
            # A. 清理可能存在的临时目录 (ModelScope 下载残留)
            temp_dir = next((child for child in model_path.iterdir() if child.name.startswith("._____temp")), None)
            if temp_dir:
                self.logger.warning(f"Found valid weights but also temporary artifacts in {model_path}. Cleaning up temp files...")
                try:
                    if temp_dir.is_dir():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    else:
                        temp_dir.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup temp dir: {e}")
            
            # B. 补全完成标记 (下次启动就不用扫盘了)
            try:
                (model_path / ".complete").touch()
                self.logger.info(f"Marked existing model as valid (Added .complete tag): {model_path}")
            except Exception:
                pass
                
            return True
            
        # 4. 如果连权重文件都没有，那就是真坏了
        self.logger.warning(f"No valid weight files found in {model_path}")
        return False

    def _install_from_hub(self, model_id: str, target_dir: Path) -> str:
        """执行下载并安装到 assets 目录"""
        self.logger.info(f"Downloading model asset '{model_id}'...")
        self.logger.info(f"Target: {target_dir}")
        
        # 确保父目录存在
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 延迟导入，无需强制依赖
            from modelscope import snapshot_download
            
            # 使用 local_dir 参数强制下载到指定目录，而不是缓存目录
            download_path = snapshot_download(
                model_id=model_id, 
                local_dir=str(target_dir),
                # 忽略一些非必要文件，保持目录整洁 (视情况而定)
                # ignore_file_pattern=[".git", "*.md"] 
            )
            
            # 下载成功后，生成完成标记
            try:
                (target_dir / ".complete").touch()
            except Exception as e:
                self.logger.warning(f"Failed to create marker file: {e}")

            self.logger.info(f"Successfully installed: {model_id}")
            return str(download_path)
            
        except ImportError:
            self.logger.error("ModelScope library not found. Cannot auto-install model.")
            raise RuntimeError("Missing dependency: modelscope")
        except Exception as e:
            self.logger.error(f"Failed to install model '{model_id}': {e}")
            
            # 安装失败时清理可能残留的文件，防止下次误判
            # 这里必须谨慎: 如果 target_dir 已经有部分文件，是否要全删?
            # 既然是 _install_from_hub 失败，且目标是我们刚指定的目录，理应清理
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise e

    def ensure_model_downloaded(self, model_id: str):
        """显式触发模型下载"""
        self.resolve_model_path(model_id, auto_download=True)

# 全局单例初始化 (确保被导入时应用环境变量)
global_model_manager = ModelManager()
