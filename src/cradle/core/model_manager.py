import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from cradle.utils.logger import logger
from cradle.utils.path import ProjectPath, get_model_path, normalize_path


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

        # 从 SystemSettings 尝试读取全局策略（若 ConfigManager 尚未初始化则忽略）
        self.default_auto_download = False
        self.weight_size_threshold_mb = 10
        self.whitelist = []
        self._load_policy_from_config()

        # 注入环境变量 (构建防污染围栏)
        self._apply_cache_sandbox_env()

        self._initialized = True

    def _load_policy_from_config(self):
        """加载模型管理全局策略（失败时使用默认值）。"""
        try:
            from cradle.core.config_manager import global_config
            sys_mm = global_config.get_system().model_manager
            self.default_auto_download = bool(sys_mm.auto_download)
            self.weight_size_threshold_mb = int(sys_mm.size_threshold_mb)
            self.whitelist = list(sys_mm.whitelist or [])
        except Exception:
            pass

    def _apply_cache_sandbox_env(self):
        """设置缓存沙盒环境变量，避免污染用户目录。"""
        sandbox = normalize_path(self.hub_cache_sandbox)
        env_map = {
            "MODELSCOPE_CACHE": sandbox,
            "HF_HOME": sandbox,
            "TORCH_HOME": sandbox,
            "XDG_CACHE_HOME": sandbox,
        }
        for env_key, env_val in env_map.items():
            os.environ[env_key] = env_val

    def _resolve_local_asset_path(self, model_identifier: str) -> Tuple[str, Path]:
        """将模型标识归一化为 (normalized_identifier, local_asset_path)。"""
        normalized = model_identifier

        if os.path.isabs(model_identifier):
            abs_path = Path(model_identifier)
            if abs_path.exists():
                return str(abs_path.resolve()), abs_path

            self.logger.warning(
                f"Configured absolute path not found: {model_identifier} — will try basename '{abs_path.name}' as repo id for auto-download if allowed"
            )
            normalized = abs_path.name

        model_name_clean = normalized.split("/")[-1]
        return normalized, get_model_path(model_name_clean)

    def _is_auto_download_allowed(self, model_identifier: str, auto_download: Optional[bool]) -> Tuple[bool, bool]:
        """根据请求参数、全局策略和白名单判定是否允许自动下载。"""
        effective_auto_download = bool(
            auto_download if auto_download is not None else self.default_auto_download)
        whitelist_allowed = True
        if self.whitelist:
            whitelist_allowed = any(
                w in model_identifier for w in self.whitelist)
            if not whitelist_allowed:
                effective_auto_download = False
        return effective_auto_download, whitelist_allowed

    def _remove_invalid_asset(self, local_asset_path: Path):
        """删除不完整或损坏的本地模型资源。"""
        if not local_asset_path.exists():
            return
        if local_asset_path.is_dir():
            shutil.rmtree(local_asset_path, ignore_errors=True)
        else:
            local_asset_path.unlink(missing_ok=True)

    def resolve_model_path(self, model_identifier: str, auto_download: bool = True) -> str:
        """
        解析模型路径。遵循 "本地优先 -> 自动安装" 策略。

        :param model_identifier: 模型ID (如 'iic/SenseVoiceSmall') 或 本地文件名
        :param auto_download: 如果本地不存在，是否允许尝试自动下载
        :return: 可供加载的绝对路径
        """
        model_identifier, local_asset_path = self._resolve_local_asset_path(
            model_identifier)

        if os.path.isabs(model_identifier):
            return model_identifier

        # 3. 本地命中检查
        # 检查是否已经存在并且完整
        if local_asset_path.exists():
            if self._validate_integrity(local_asset_path):
                self.logger.info(
                    f"Using verified local asset: {local_asset_path}")
                return str(local_asset_path.resolve())
            else:
                self.logger.warning(
                    f"Model integrity check failed for {local_asset_path}. Re-installing...")
                self._remove_invalid_asset(local_asset_path)

        # 4. 自动安装流程（受限于全局策略与白名单）
        effective_auto_download, whitelist_allowed = self._is_auto_download_allowed(
            model_identifier, auto_download)

        # 结构化日志：决策原因（本地/自动下载/白名单）
        self.logger.debug(
            "[ModelManager][resolve] decision",
            extra={
                "model_id": model_identifier,
                "local_path": str(local_asset_path),
                "exists": local_asset_path.exists(),
                "auto_download_requested": bool(auto_download),
                "effective_auto_download": effective_auto_download,
                "whitelist_configured": bool(self.whitelist),
                "whitelist_allowed": whitelist_allowed,
            },
        )

        if effective_auto_download:
            return self._install_from_hub(model_identifier, local_asset_path)

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

        # 2. 深度扫描: 寻找核心权重文件 + 检查模型格式（transformers / sentence-transformers）
        # 定义可能的权重文件后缀
        weight_suffixes = {'.pt', '.bin',
                           '.safetensors', '.onnx', '.engine', '.model'}
        valid_weights_found = False
        min_size_bytes = int(self.weight_size_threshold_mb) * 1024 * 1024

        try:
            # 遍历一级目录 (通常权重在根目录)
            for file in model_path.iterdir():
                if file.is_file() and file.suffix in weight_suffixes:
                    # 使用可配置的大小阈值进行判断，避免只是个占位符
                    if file.stat().st_size > min_size_bytes:
                        valid_weights_found = True
                        break
        except Exception:
            pass  # 权限问题等

        # 额外格式验证：检查 config.json 中是否包含 transformers 所需的 model_type
        # 或者目录中存在 sentence-transformers 的特征文件（sentence_bert_config.json）
        format_compatible = False
        try:
            cfg_json = model_path / 'config.json'
            sbt_cfg = model_path / 'sentence_bert_config.json'
            if sbt_cfg.exists():
                # 明确为 sentence-transformers 包装模型
                format_compatible = True
            if cfg_json.exists():
                try:
                    import json
                    data = json.loads(cfg_json.read_text(encoding='utf-8'))
                    if 'model_type' in data or 'architectures' in data:
                        # transformers 可识别的配置
                        format_compatible = True
                except Exception:
                    pass
        except Exception:
            pass

        # 若无有效权重，直接判定无效
        if not valid_weights_found:
            self.logger.warning(f"No valid weight files found in {model_path}")
            return False

        # 如果有有效权重但格式不兼容，判定无效（触发重装）
        if not format_compatible:
            self.logger.warning(
                f"Weights found in {model_path} but no compatible model config detected.")
            return False

        # 3. 结果判定与自动维护
        # A. 清理可能存在的临时目录 (ModelScope 下载残留)
        temp_dir = next((child for child in model_path.iterdir()
                        if child.name.startswith("._____temp")), None)
        if temp_dir:
            self.logger.warning(
                f"Found valid weights but also temporary artifacts in {model_path}. Cleaning up temp files...")
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
            self.logger.info(
                f"Marked existing model as valid (Added .complete tag): {model_path}")
        except Exception:
            pass

        return True

    def _install_from_hub(self, model_id: str, target_dir: Path) -> str:
        """执行下载并安装到 assets 目录"""
        self.logger.info(f"Downloading model asset '{model_id}'...")
        self.logger.info(f"Target: {target_dir}")

        # 确保父目录存在
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        # 结构化日志：开始安装尝试（包含目标目录与策略）
        self.logger.info("[ModelManager][install] start", extra={
            "model_id": model_id,
            "target_dir": str(target_dir),
        })

        last_err = None

        try:
            return self._download_from_modelscope(model_id, target_dir)
        except Exception as e:
            last_err = e
            self.logger.debug("[模型管理器][安装] ModelScope 下载失败",
                              extra={"error": repr(e)})

        try:
            return self._download_from_huggingface(model_id, target_dir)
        except Exception as e2:
            self.logger.error("[ModelManager][install] all sources failed", extra={
                              "model_id": model_id, "error": repr(e2), "last_err": repr(last_err)})
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise RuntimeError(e2)

    def _download_from_modelscope(self, model_id: str, target_dir: Path) -> str:
        from modelscope import snapshot_download as ms_snapshot

        self.logger.debug("[ModelManager][install] trying source", extra={
                          "source": "modelscope", "model_id": model_id})
        download_path = ms_snapshot(
            model_id=model_id, local_dir=str(target_dir))
        self._touch_complete_marker(target_dir)
        self.logger.info("[模型管理器][安装成功]", extra={
                         "source": "modelscope", "model_id": model_id, "path": str(download_path)})
        return str(download_path)

    def _download_from_huggingface(self, model_id: str, target_dir: Path) -> str:
        from huggingface_hub import snapshot_download as hf_snapshot

        self.logger.debug("[模型管理器][安装] 尝试来源", extra={
                          "source": "huggingface", "model_id": model_id})
        hf_snapshot(repo_id=model_id, local_dir=str(target_dir),
                    local_dir_use_symlinks=False, resume_download=True)
        self._touch_complete_marker(target_dir)
        self.logger.info("[模型管理器][安装成功]", extra={
                         "source": "huggingface", "model_id": model_id, "path": str(target_dir)})
        return str(target_dir)

    def _touch_complete_marker(self, target_dir: Path):
        try:
            (target_dir / ".complete").touch()
        except Exception as e:
            self.logger.warning(f"Failed to create marker file: {e}")

    def ensure_model_downloaded(self, model_id: str):
        """显式触发模型下载"""
        self.resolve_model_path(model_id, auto_download=True)


# 全局单例初始化 (确保被导入时应用环境变量)
global_model_manager = ModelManager()
