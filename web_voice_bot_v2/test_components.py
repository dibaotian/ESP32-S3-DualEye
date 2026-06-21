#!/usr/bin/env python3
"""
Test script to verify all components are working
"""

import sys
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_asr_service():
    """Test ASR Service connectivity"""
    try:
        url = "http://localhost:8101/health"
        response = httpx.get(url, timeout=5.0)
        if response.status_code == 200:
            logger.info("✓ ASR Service (port 8101) is healthy")
            return True
        else:
            logger.error(f"✗ ASR Service returned status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"✗ Cannot connect to ASR Service: {e}")
        logger.error("  Please start ASR_Service on port 8101")
        return False


def test_vllm_service():
    """Test vLLM Service connectivity"""
    try:
        url = "http://localhost:8102/health"
        response = httpx.get(url, timeout=5.0)
        if response.status_code == 200:
            logger.info("✓ vLLM Service (port 8102) is healthy")
            return True
        else:
            logger.error(f"✗ vLLM Service returned status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"✗ Cannot connect to vLLM Service: {e}")
        logger.error("  Please start vLLM Service on port 8102")
        return False


def test_pytorch():
    """Test PyTorch installation"""
    try:
        import torch
        logger.info(f"✓ PyTorch {torch.__version__} installed")
        if torch.cuda.is_available():
            logger.info(f"  GPU: {torch.cuda.get_device_name(0)}")
        else:
            logger.info("  Using CPU")
        return True
    except Exception as e:
        logger.error(f"✗ PyTorch not installed: {e}")
        return False


def test_silero_vad():
    """Test Silero VAD model loading"""
    try:
        import torch
        logger.info("Loading Silero VAD model...")
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
        )
        logger.info("✓ Silero VAD model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to load Silero VAD: {e}")
        return False


def test_melo_tts():
    """Test MeloTTS installation"""
    try:
        from melo.api import TTS
        import torch

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Loading MeloTTS on {device}...")

        tts = TTS(language='ZH', device=device)
        logger.info("✓ MeloTTS loaded successfully")
        return True
    except ImportError:
        logger.error("✗ MeloTTS not installed")
        logger.error("  Install with: pip install melo-tts")
        return False
    except Exception as e:
        logger.error(f"✗ Failed to load MeloTTS: {e}")
        return False


def test_flask_socketio():
    """Test Flask-SocketIO installation"""
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        logger.info("✓ Flask and Flask-SocketIO installed")
        return True
    except Exception as e:
        logger.error(f"✗ Flask-SocketIO not installed: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("DualEye Voice Bot v2 - Component Tests")
    logger.info("=" * 60)
    logger.info("")

    results = []

    logger.info("Testing Python packages...")
    results.append(("PyTorch", test_pytorch()))
    results.append(("Flask-SocketIO", test_flask_socketio()))
    results.append(("Silero VAD", test_silero_vad()))
    results.append(("MeloTTS", test_melo_tts()))

    logger.info("")
    logger.info("Testing external services...")
    results.append(("ASR Service", test_asr_service()))
    results.append(("vLLM Service", test_vllm_service()))

    logger.info("")
    logger.info("=" * 60)
    logger.info("Test Results:")
    logger.info("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False

    logger.info("")
    if all_passed:
        logger.info("✓ All tests passed! Ready to start the server.")
        logger.info("  Run: python app.py")
        return 0
    else:
        logger.error("✗ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
