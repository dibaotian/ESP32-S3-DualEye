#!/bin/bash
# DualEye Voice Bot v2 - Installation Script

set -e

echo "=================================="
echo "DualEye Voice Bot v2 - 安装脚本"
echo "=================================="
echo ""

# Check Python version
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本: $python_version"

if ! python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
    echo "错误: 需要 Python 3.10 或更高版本"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# Activate virtual environment
echo ""
echo "激活虚拟环境..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "升级 pip..."
pip install --upgrade pip

# Install PyTorch (check for CUDA)
echo ""
echo "安装 PyTorch..."
if command -v nvidia-smi &> /dev/null; then
    echo "检测到 NVIDIA GPU，安装 CUDA 版本 PyTorch..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "未检测到 GPU，安装 CPU 版本 PyTorch..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

# Install requirements
echo ""
echo "安装项目依赖..."
pip install -r requirements.txt

# Install soundfile for audio I/O
echo ""
echo "安装音频处理库..."
pip install soundfile

# Download Silero VAD model (will be cached by torch.hub)
echo ""
echo "预下载 Silero VAD 模型..."
python3 -c "import torch; torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)"

echo ""
echo "=================================="
echo "安装完成!"
echo "=================================="
echo ""
echo "下一步:"
echo "1. 确保 ASR_Service 运行在端口 8101"
echo "2. 确保 vLLM Service 运行在端口 8102"
echo "3. 运行: python app.py"
echo ""
echo "或使用启动脚本: ./start.sh"
echo ""
