// Audio Worklet Processor
// Processes microphone audio and sends to main thread

class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 4096;
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
        this.callCount = 0;
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];

        // Report first few process() calls to main thread for diagnostics
        if (this.callCount < 3) {
            this.port.postMessage({
                debug: true,
                call: this.callCount,
                inputChannels: input ? input.length : 0,
                samples: (input && input[0]) ? input[0].length : 0,
            });
            this.callCount++;
        }

        if (input.length > 0) {
            const channelData = input[0];  // Mono channel

            for (let i = 0; i < channelData.length; i++) {
                this.buffer[this.bufferIndex++] = channelData[i];

                // When buffer is full, send to main thread
                if (this.bufferIndex >= this.bufferSize) {
                    // Convert Float32Array to ArrayBuffer for transfer
                    const audioData = this.buffer.slice(0, this.bufferIndex);
                    const arrayBuffer = audioData.buffer.slice(
                        audioData.byteOffset,
                        audioData.byteOffset + audioData.byteLength
                    );

                    this.port.postMessage(arrayBuffer, [arrayBuffer]);

                    // Reset buffer
                    this.bufferIndex = 0;
                }
            }
        }

        return true;  // Keep processor alive
    }
}

registerProcessor('audio-processor', AudioProcessor);
