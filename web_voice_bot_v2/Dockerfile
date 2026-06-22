# DualEye Voice Bot v2 - Docker Image
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（含ffmpeg用于MP3解码；gnupg/ca-certificates 供 NodeSource）
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 22 + Codex CLI（Codex 作为对话大脑,跑在本地 vLLM 上）
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @openai/codex@0.135.0 \
    && rm -rf /var/lib/apt/lists/* \
    && codex --version

# 安装Python依赖
RUN pip install --no-cache-dir \
    'flask>=3.0.0' \
    'flask-socketio>=5.3.0' \
    'python-socketio>=5.10.0' \
    'httpx>=0.27.0' \
    'numpy>=1.26.0' \
    'soundfile>=0.12.1' \
    'edge-tts>=7.0.0' && \
    pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir 'sentence-transformers>=3.0.0'

# 预下载向量记忆嵌入模型 bge-small-zh-v1.5（避免运行时联网）
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5', device='cpu'); print('bge model cached')"

# 复制应用代码
COPY . .

# 预下载Silero VAD模型（避免运行时交互）
RUN python3 << 'PYEOF'
import torch
import os
os.environ['TORCH_HOME'] = '/tmp/torch'
try:
    # 预先下载VAD模型
    torch.hub.set_dir('/app/models')
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        trust_repo=True
    )
    print("VAD model downloaded successfully")
except Exception as e:
    print(f"Warning: Could not pre-download VAD model: {e}")
PYEOF

# 嵌入模型已在构建时缓存 → 运行时离线加载,避免联网检查
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    AGENT_BACKEND=codex

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888 || exit 1

# 启动命令
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8888"]
