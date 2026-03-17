import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import uuid

import pytest
import zmq
import zmq.asyncio


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_kernel_to_python_integration_end_to_end():
    """完整集成测试：模拟内核 Router 与 Python AI Dealer 通信"""

    # Windows 上该用例在部分环境中存在 ROUTER/DEALER 首包时序不稳定，容易产生假死。
    if os.name == "nt":
        pytest.skip("Windows 下跳过该低层时序测试，使用内核端到端用例覆盖。")

    # 1) 准备配置：不依赖任何真实服务
    port = _find_free_port()
    bind_addr = f"tcp://127.0.0.1:{port}"

    # minimal config for python -> will run in local llm mode
    config = {
        "persona": {
            "base": {
                "name": "x",
                "nickname": "x",
                "age": 1,
                "gender": "x",
                "core_identity": "x",
                "self_description": "x",
            },
            "character_traits": {},
            "behavior_rules": [],
            "boundary_limits": [],
        },
        "inference": {
            "model": {
                "local_model_path": "/tmp",
                "max_tokens": 16,
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
            },
            "life_clock": {"thought_interval_ms": 1000},
            "memory": {"max_recall_count": 5, "retention_days": 30},
        },
        "llm": {"api_type": "local"},
    }

    env = os.environ.copy()
    env["SELRENA_CONFIG"] = json.dumps(config)
    env["SELRENA_IPC_BIND_ADDRESS"] = bind_addr

    # Ensure the python package can be imported when invoking `python -m selrena.main`
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_path = os.path.join(repo_root, "core", "cradle-selrena-core", "src")
    env["PYTHONPATH"] = os.pathsep.join([src_path, env.get("PYTHONPATH", "")])

    # 2) 启动 Python AI 进程
    python_exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
    proc = subprocess.Popen(
        [python_exe, "-m", "selrena.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    try:
        # 3) 启动 Router 服务器并等待 Python 连接
        async def _run_router_test():
            ctx = zmq.asyncio.Context()
            router = ctx.socket(zmq.ROUTER)
            router.bind(bind_addr)

            # 等待 python AI 发送第一条状态同步数据
            client_id = None
            for _ in range(30):
                try:
                    msg_parts = await router.recv_multipart()
                    if len(msg_parts) not in (2, 3):
                        continue
                    if len(msg_parts) == 3:
                        client_id, _, msg_bytes = msg_parts
                    else:
                        client_id, msg_bytes = msg_parts
                    data = json.loads(msg_bytes.decode("utf-8"))
                    # 内容格式可能为 state_sync / memory_sync 等
                    if data.get("type") == "state_sync":
                        break
                except Exception:
                    await asyncio.sleep(0.1)
            assert client_id is not None, "未收到 python AI 的 state_sync 消息"

            # 4) 发送 Chat 请求到 python
            trace_id = str(uuid.uuid4())
            request = {
                "type": "chat_message",
                "trace_id": trace_id,
                "user_input": "你好",
                "scene_id": "test",
                "familiarity": 0,
            }
            await router.send_multipart([client_id, json.dumps(request).encode("utf-8")])

            # 5) 接收 python 回复
            reply = None
            for _ in range(30):
                msg_parts = await router.recv_multipart()
                if len(msg_parts) not in (2, 3):
                    continue
                if len(msg_parts) == 3:
                    resp_client_id, _, resp_bytes = msg_parts
                else:
                    resp_client_id, resp_bytes = msg_parts
                if resp_client_id != client_id:
                    continue
                reply = json.loads(resp_bytes.decode("utf-8"))
                break

            assert reply is not None, "未收到 python AI 的回复"
            assert reply.get("type") == "success"
            assert isinstance(reply.get("data"), dict)
            assert "reply_content" in reply["data"]

            # 关闭
            router.close()
            ctx.term()

        # 4) 运行 Router 测试逻辑
        asyncio.run(asyncio.wait_for(_run_router_test(), timeout=15))

    finally:
        # 先停止子进程，再做带超时的输出收集，避免 read() 阻塞导致测试卡死。
        try:
            proc.terminate()
            out, err = proc.communicate(timeout=3)
            out = (out or "").strip()
            err = (err or "").strip()
            if out:
                print("--- python stdout ---")
                print(out)
            if err:
                print("--- python stderr ---")
                print(err)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            proc.kill()


def test_kernel_and_python_integration_end_to_end():
    """完整集成测试：启动 TS 内核（含 Python AI），通过内核的 IPC 发送 chat_message 并收回回复"""
    import shutil
    import tempfile

    # 如果本地没有 pnpm/node，则跳过
    if shutil.which("pnpm") is None or shutil.which("node") is None:
        pytest.skip("需要 pnpm/node 环境才能运行内核集成测试")

    # 1) 准备临时配置目录（不污染仓库）
    with tempfile.TemporaryDirectory() as tmpdir:
        configs_dir = os.path.join(tmpdir, "configs")
        os.makedirs(configs_dir, exist_ok=True)

        # minimal configs
        open(os.path.join(configs_dir, "general.yaml"), "w", encoding="utf-8").write(
            "app_name: \"test\"\napp_version: \"0.0.1\"\nlog_level: \"debug\"\ndata_dir: \"data\"\nlog_dir: \"logs\"\nbackup_dir: \"data/backup\"\nauto_backup_interval_hours: 24\n"
        )

        os.makedirs(os.path.join(configs_dir, "python-ai"), exist_ok=True)
        open(os.path.join(configs_dir, "python-ai", "inference.yaml"), "w", encoding="utf-8").write(
            "inference:\n  model:\n    local_model_path: \"/tmp\"\n    max_tokens: 16\n    temperature: 0.7\n    top_p: 0.9\n    frequency_penalty: 0.0\n  life_clock:\n    thought_interval_ms: 1000\n  memory:\n    max_recall_count: 5\n    retention_days: 30\n    context_limit: 5\n"
        )
        open(os.path.join(configs_dir, "python-ai", "persona.yaml"), "w", encoding="utf-8").write(
            "persona:\n  base:\n    name: \"x\"\n    nickname: \"x\"\n    age: 1\n    gender: \"x\"\n    core_identity: \"x\"\n    self_description: \"x\"\n  character_traits: {}\n  behavior_rules: []\n  boundary_limits: []\n"
        )
        open(os.path.join(configs_dir, "python-ai", "llm.yaml"), "w", encoding="utf-8").write(
            "api_type: \"local\"\napi_key: \"\"\nbase_url: \"\"\nmodel: \"\"\ntemperature: 0.7\n"
        )

        os.makedirs(os.path.join(configs_dir, "kernel"), exist_ok=True)
        port = _find_free_port()
        bind_addr = f"tcp://127.0.0.1:{port}"
        open(os.path.join(configs_dir, "kernel", "ipc.yaml"), "w", encoding="utf-8").write(
            f"bind_address: \"{bind_addr}\"\nrequest_timeout_ms: 30000\nretry_count: 2\nretry_interval_ms: 2000\nheartbeat_interval_ms: 5000\n"
        )
        open(os.path.join(configs_dir, "kernel", "lifecycle.yaml"), "w", encoding="utf-8").write(
            "start_timeout_ms: 30000\nstop_timeout_ms: 30000\nmodule_start_order: [\"config\", \"persistence\", \"ipc\", \"python_ai\", \"plugins\", \"life_clock\"]\nmodule_stop_order: [\"life_clock\", \"plugins\", \"python_ai\", \"ipc\", \"persistence\", \"config\"]\n"
        )
        open(os.path.join(configs_dir, "kernel", "memory.yaml"), "w", encoding="utf-8").write(
            "max_recall_count: 5\nretention_days: 30\ncontext_limit: 5\n"
        )
        open(os.path.join(configs_dir, "kernel", "plugin.yaml"), "w", encoding="utf-8").write(
            "plugin_root_dir: \"plugins\"\n\nsandbox:\n  enable_isolation: true\n  timeout_ms: 5000\n  allow_native_modules: false\n\ndefault_permissions: []\nplugin_blacklist: []\n"
        )

        # ensure plugin dir exists to avoid startup errors
        os.makedirs(os.path.join(tmpdir, "plugins"), exist_ok=True)

        # 2) 启动内核（TS 进程）
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        kernel_dir = os.path.join(repo_root, "core", "kernel")
        cmd = [
            "pnpm",
            "-C",
            kernel_dir,
            "run",
            "dev",
        ]

        proc = subprocess.Popen(
            cmd,
            cwd=tmpdir,
            env={**os.environ, "NODE_ENV": "test"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        try:
            # 让内核和 Python AI 启动起来
            time.sleep(10)

            # 3) 通过内核 IPC 发送 chat_message 并等待回复
            ctx = zmq.Context()
            req = ctx.socket(zmq.REQ)
            req.connect(bind_addr)

            trace_id = str(uuid.uuid4())
            request = {
                "type": "chat_message",
                "trace_id": trace_id,
                "payload": {
                    "user_input": "hello",
                    "scene_id": "test",
                    "familiarity": 0,
                },
            }

            req.send_json(request)
            reply = req.recv_json(flags=0)

            assert reply.get("type") == "success_response"
            assert reply.get("success") is True
            assert reply.get("data") and "reply_content" in reply["data"]

        finally:
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=5)
                out = (out or "").strip()
                err = (err or "").strip()
                if out:
                    print("--- kernel stdout ---")
                    print(out)
                if err:
                    print("--- kernel stderr ---")
                    print(err)
            except subprocess.TimeoutExpired:
                proc.kill()
