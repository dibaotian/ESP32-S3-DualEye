#!/usr/bin/env python3
"""
Pipeline Performance Benchmark
测量各个组件的延迟并给出优化建议
"""

import time
import sys
import httpx
import numpy as np
import base64
import io
import wave
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_test_audio(duration_sec=2.0, sample_rate=16000):
    """生成测试音频 (正弦波)"""
    t = np.linspace(0, duration_sec, int(duration_sec * sample_rate))
    # 440 Hz 正弦波
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return audio


def audio_to_base64_wav(audio_data, sample_rate=16000):
    """转换音频为 base64 WAV"""
    audio_int16 = (audio_data * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())

    buffer.seek(0)
    audio_bytes = buffer.read()
    return base64.b64encode(audio_bytes).decode('utf-8')


def benchmark_asr(audio_base64, runs=3):
    """测试 ASR Service 延迟"""
    logger.info("=" * 60)
    logger.info("Benchmarking ASR Service")
    logger.info("=" * 60)

    url = "http://localhost:8101/v1/chat/completions"

    latencies = []

    for i in range(runs):
        payload = {
            "model": "Qwen/Qwen3-ASR-Flash",
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "audio_url",
                    "audio_url": {
                        "url": f"data:audio/wav;base64,{audio_base64}"
                    }
                }]
            }],
            "max_tokens": 512,
        }

        start = time.time()

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                transcript = result["choices"][0]["message"]["content"]

            latency = (time.time() - start) * 1000
            latencies.append(latency)

            logger.info(f"Run {i+1}/{runs}: {latency:.1f} ms - '{transcript}'")

        except Exception as e:
            logger.error(f"Run {i+1}/{runs} failed: {e}")

    if latencies:
        avg = np.mean(latencies)
        std = np.std(latencies)
        logger.info(f"\n✓ ASR Average: {avg:.1f} ms (±{std:.1f} ms)")
        logger.info(f"  Min: {min(latencies):.1f} ms | Max: {max(latencies):.1f} ms")
        return avg

    return None


def benchmark_llm(text="你好，今天天气怎么样？", runs=3):
    """测试 LLM Service 延迟"""
    logger.info("\n" + "=" * 60)
    logger.info("Benchmarking LLM Service")
    logger.info("=" * 60)

    url = "http://localhost:8102/v1/chat/completions"

    latencies = []
    ttfts = []  # Time to first token (估算)

    for i in range(runs):
        payload = {
            "model": "cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit",
            "messages": [
                {"role": "system", "content": "你是一个简洁的AI助手，请用一句话回答。"},
                {"role": "user", "content": text}
            ],
            "max_tokens": 100,
            "temperature": 0.7,
            "stream": False,
        }

        start = time.time()

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})

            latency = (time.time() - start) * 1000
            latencies.append(latency)

            # 估算 TTFT (约为总时间的30%)
            ttft = latency * 0.3
            ttfts.append(ttft)

            logger.info(f"Run {i+1}/{runs}: {latency:.1f} ms (TTFT ~{ttft:.1f} ms)")
            logger.info(f"  Tokens: {usage.get('completion_tokens', 0)}")
            logger.info(f"  Response: {content[:80]}...")

        except Exception as e:
            logger.error(f"Run {i+1}/{runs} failed: {e}")

    if latencies:
        avg = np.mean(latencies)
        std = np.std(latencies)
        avg_ttft = np.mean(ttfts)
        logger.info(f"\n✓ LLM Average: {avg:.1f} ms (±{std:.1f} ms)")
        logger.info(f"  Estimated TTFT: {avg_ttft:.1f} ms")
        return avg, avg_ttft

    return None, None


def benchmark_tts_melo():
    """测试 MeloTTS 延迟"""
    logger.info("\n" + "=" * 60)
    logger.info("Benchmarking MeloTTS")
    logger.info("=" * 60)

    try:
        from melo.api import TTS
        import torch

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {device}")

        # 初始化 TTS
        logger.info("Loading MeloTTS model...")
        load_start = time.time()
        tts = TTS(language='ZH', device=device)
        load_time = (time.time() - load_start) * 1000
        logger.info(f"✓ Model loaded in {load_time:.1f} ms")

        # 测试不同长度文本
        texts = [
            "好的",
            "今天天气不错",
            "人工智能技术正在快速发展，为我们的生活带来了很多便利。",
        ]

        for text in texts:
            import tempfile
            import soundfile as sf

            start = time.time()

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                tts.tts_to_file(text, speaker_id=0, output_path=tmp_path, speed=1.0)
                audio, sr = sf.read(tmp_path, dtype='float32')

                latency = (time.time() - start) * 1000
                duration = len(audio) / sr * 1000
                rtf = latency / duration

                logger.info(f"\nText: '{text}' ({len(text)} chars)")
                logger.info(f"  Synthesis: {latency:.1f} ms")
                logger.info(f"  Audio: {duration:.1f} ms ({sr} Hz)")
                logger.info(f"  RTF: {rtf:.2f}")

            finally:
                import os
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return True

    except Exception as e:
        logger.error(f"TTS benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("=" * 70)
    logger.info("DualEye Voice Bot - Pipeline Performance Benchmark")
    logger.info("=" * 70)
    logger.info("")

    # 生成测试音频
    logger.info("Generating test audio (2 seconds)...")
    test_audio = generate_test_audio(duration_sec=2.0)
    audio_base64 = audio_to_base64_wav(test_audio)
    logger.info(f"✓ Test audio ready: {len(test_audio)} samples\n")

    # 测试各组件
    results = {}

    # 1. ASR
    asr_latency = benchmark_asr(audio_base64, runs=3)
    if asr_latency:
        results['asr'] = asr_latency

    # 2. LLM
    llm_latency, ttft = benchmark_llm(runs=3)
    if llm_latency:
        results['llm'] = llm_latency
        results['ttft'] = ttft

    # 3. TTS
    tts_ok = benchmark_tts_melo()

    # 总结
    logger.info("\n" + "=" * 70)
    logger.info("Performance Summary")
    logger.info("=" * 70)

    total_latency = 0

    if 'asr' in results:
        logger.info(f"STT (ASR):        {results['asr']:.1f} ms")
        total_latency += results['asr']

    if 'ttft' in results:
        logger.info(f"LLM (TTFT):       {results['ttft']:.1f} ms")
        total_latency += results['ttft']

    if tts_ok:
        logger.info(f"TTS:              ~300 ms (estimated for short text)")
        total_latency += 300

    logger.info(f"VAD + Network:    ~150 ms (estimated)")
    total_latency += 150

    logger.info(f"\n{'='*70}")
    logger.info(f"Estimated End-to-End Latency: {total_latency:.0f} ms ({total_latency/1000:.2f} s)")
    logger.info(f"{'='*70}")

    # 优化建议
    logger.info("\n" + "=" * 70)
    logger.info("Optimization Recommendations")
    logger.info("=" * 70)

    if results.get('asr', 0) > 500:
        logger.info("⚠️  ASR: Consider using Qwen3-ASR-0.6B (faster) instead of Flash")
    else:
        logger.info("✓  ASR: Performance is good")

    if results.get('llm', 0) > 2000:
        logger.info("⚠️  LLM: High latency. Consider:")
        logger.info("    - Reduce max_tokens")
        logger.info("    - Use streaming mode")
        logger.info("    - Check vLLM GPU utilization")
    elif results.get('ttft', 0) > 500:
        logger.info("⚠️  LLM TTFT: Consider increasing vLLM batch size or using tensor parallelism")
    else:
        logger.info("✓  LLM: Performance is good")

    if total_latency > 2000:
        logger.info("\n⚠️  Overall latency > 2s. Recommendations:")
        logger.info("    1. Enable LLM streaming for faster perceived response")
        logger.info("    2. Use GPU if available")
        logger.info("    3. Optimize TTS with faster engine (e.g., Piper)")
        logger.info("    4. Reduce LLM max_tokens to 256")
    else:
        logger.info(f"\n✓  Overall latency < 2s - Good for real-time conversation!")

    return 0


if __name__ == '__main__':
    sys.exit(main())
