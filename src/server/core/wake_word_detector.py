"""
WakeWordDetector - Server-side wake word detection using openWakeWord
"""
import asyncio
import logging
import numpy as np
from typing import AsyncGenerator, Optional, Union
from dataclasses import dataclass
import time
import base64
from openwakeword.model import Model

logger = logging.getLogger(__name__)

@dataclass
class WakeWordEvent:
    """Event emitted when a wake word is detected"""
    wake_word: str
    confidence: float
    timestamp: float
    client_id: str
    detected: bool = True

@dataclass
class WakeWordStatus:
    """Status update with current detection scores"""
    scores: dict  # model_name -> confidence score
    timestamp: float
    client_id: str
    detected: bool = False

class WakeWordDetector:
    """Continuous wake word detection using openWakeWord model"""
    
    def __init__(self, client_id: str, model_path: str = None, threshold: float = 0.2):
        """
        Initialize wake word detector for a specific client
        
        Args:
            client_id: Unique identifier for the client
            model_path: Path to the openWakeWord model file (if None, uses default luna.onnx)
            threshold: Detection confidence threshold (0.0-1.0)
        """
        self.client_id = client_id
        
        # Set default model path to the luna.onnx file in the same directory
        if model_path is None:
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.model_path = os.path.join(current_dir, "luna.onnx")
        else:
            self.model_path = model_path
            
        self.threshold = threshold
        self.audio_queue = asyncio.Queue()
        self.is_running = False
        
        # Audio parameters - matching the demo script
        self.source_sample_rate = 24000  # Client sends 24kHz audio
        self.target_sample_rate = 16000  # openWakeWord expects 16kHz
        self.chunk_size = 1280  # Samples per chunk at 16kHz (from demo)
        
        # Audio buffer for resampling and chunk accumulation - with size limits for memory management
        self.max_buffer_size = self.source_sample_rate * 5  # Maximum 5 seconds of audio
        self.source_buffer = np.array([], dtype=np.int16)
        self.target_buffer = np.array([], dtype=np.int16)
        
        # Initialize the openWakeWord model
        self.oww_model = None
        
        logger.info(f"[WAKE_WORD] Initialized detector for client {client_id} with model '{model_path}' and threshold {threshold}")
    
    async def start(self) -> AsyncGenerator[Union[WakeWordEvent, WakeWordStatus], None]:
        """
        Start wake word detection and yield events when wake words are detected
        
        Yields:
            WakeWordStatus objects with current scores (periodically)
            WakeWordEvent objects when wake words are detected
        """
        self.is_running = True
        logger.info(f"[WAKE_WORD] Starting detection for client {self.client_id}")
        
        try:
            # Initialize openWakeWord model
            await self._initialize_model()
            
            # Process audio chunks continuously
            while self.is_running:
                try:
                    # Get audio chunk with timeout to allow for graceful shutdown
                    audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
                    
                    # Add to resampling buffer
                    self._add_to_buffer(audio_chunk)
                    
                    # Process accumulated chunks if we have enough data
                    async for event in self._process_accumulated_audio():
                        yield event
                    
                except asyncio.TimeoutError:
                    # Timeout is expected - allows for graceful shutdown checking
                    continue
                except Exception as e:
                    logger.error(f"[WAKE_WORD] Error processing audio for client {self.client_id}: {e}")
                    await asyncio.sleep(0.1)  # Brief pause before retrying
                    
        except Exception as e:
            logger.error(f"[WAKE_WORD] Fatal error in wake word detection for client {self.client_id}: {e}")
        finally:
            logger.info(f"[WAKE_WORD] Stopped detection for client {self.client_id}")
    
    def add_audio_chunk(self, audio_data: bytes):
        """
        Add audio chunk to processing queue (non-blocking)
        
        Args:
            audio_data: Raw PCM audio data (24kHz, 16-bit, mono)
        """
        if self.is_running:
            try:
                # Convert bytes to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                self.audio_queue.put_nowait(audio_array)
            except asyncio.QueueFull:
                logger.warning(f"[WAKE_WORD] Audio queue full for client {self.client_id}, dropping chunk")
            except Exception as e:
                logger.error(f"[WAKE_WORD] Error adding audio chunk for client {self.client_id}: {e}")
    
    def stop(self):
        """Stop wake word detection"""
        self.is_running = False
        logger.info(f"[WAKE_WORD] Stopping detection for client {self.client_id}")
    
    async def _initialize_model(self):
        """Initialize the openWakeWord model"""
        try:
            import os
            
            # Check if the model file exists at the specified path
            if os.path.exists(self.model_path):
                # Use absolute path for custom model
                absolute_model_path = os.path.abspath(self.model_path)
                logger.info(f"[WAKE_WORD] Loading custom model from: {absolute_model_path}")
                self.oww_model = Model(wakeword_models=[absolute_model_path], inference_framework='onnx')
            else:
                # If custom model doesn't exist, fall back to default models
                logger.warning(f"[WAKE_WORD] Custom model not found at {self.model_path}, falling back to default models")
                # Download default models if not already available
                import openwakeword
                openwakeword.utils.download_models()
                # Load default models (this will load all available default models)
                self.oww_model = Model(inference_framework='onnx')
            
            logger.info(f"[WAKE_WORD] OpenWakeWord model initialized for client {self.client_id}")
            logger.info(f"[WAKE_WORD] Available models: {list(self.oww_model.models.keys())}")
            
        except Exception as e:
            logger.error(f"[WAKE_WORD] Failed to initialize model for client {self.client_id}: {e}")
            # Try one more fallback - load without any specific models
            try:
                logger.info(f"[WAKE_WORD] Attempting fallback initialization for client {self.client_id}")
                import openwakeword
                openwakeword.utils.download_models()
                self.oww_model = Model(inference_framework='onnx')
                logger.info(f"[WAKE_WORD] Fallback model loaded successfully for client {self.client_id}")
                logger.info(f"[WAKE_WORD] Available fallback models: {list(self.oww_model.models.keys())}")
            except Exception as fallback_error:
                logger.error(f"[WAKE_WORD] Fallback initialization also failed for client {self.client_id}: {fallback_error}")
                raise
    
    def _add_to_buffer(self, audio_chunk: np.ndarray):
        """Add audio chunk to the source buffer for resampling with memory management"""
        self.source_buffer = np.concatenate([self.source_buffer, audio_chunk])
        
        # Prevent buffer from growing too large - keep only recent audio
        if len(self.source_buffer) > self.max_buffer_size:
            # Keep only the last max_buffer_size samples
            self.source_buffer = self.source_buffer[-self.max_buffer_size:]
            logger.debug(f"[WAKE_WORD] Trimmed source buffer for client {self.client_id} to prevent memory growth")
    
    async def _process_accumulated_audio(self) -> AsyncGenerator[Union[WakeWordEvent, WakeWordStatus], None]:
        """Process accumulated audio data and yield wake word events and status updates"""
        # Resample accumulated audio from 24kHz to 16kHz
        resampled_audio = self._resample_audio()
        
        if len(resampled_audio) == 0:
            return
            
        # Add resampled audio to target buffer
        self.target_buffer = np.concatenate([self.target_buffer, resampled_audio])
        
        # Process in chunks of the specified chunk size
        while len(self.target_buffer) >= self.chunk_size:
            # Extract chunk for processing
            chunk = self.target_buffer[:self.chunk_size]
            self.target_buffer = self.target_buffer[self.chunk_size:]
            
            # Prevent target buffer from accumulating too much
            max_target_buffer = self.chunk_size * 10  # Keep max 10 chunks
            if len(self.target_buffer) > max_target_buffer:
                self.target_buffer = self.target_buffer[-max_target_buffer:]
                logger.debug(f"[WAKE_WORD] Trimmed target buffer for client {self.client_id}")
            
            # Run wake word detection on this chunk
            detection_result = await self._detect_wake_word(chunk)
            
            if detection_result:
                if detection_result['detected']:
                    # Yield wake word event
                    event = WakeWordEvent(
                        wake_word=detection_result['wake_word'],
                        confidence=detection_result['confidence'],
                        timestamp=time.time(),
                        client_id=self.client_id,
                        detected=True
                    )
                    logger.info(f"[WAKE_WORD] Wake word '{detection_result['wake_word']}' detected for client {self.client_id} with confidence {detection_result['confidence']:.3f}")
                    yield event
                    
                    # Clear buffers after detection to avoid immediate re-detection
                    self._clear_buffers()
                else:
                    # Yield status update with current scores
                    status = WakeWordStatus(
                        scores=detection_result['scores'],
                        timestamp=time.time(),
                        client_id=self.client_id,
                        detected=False
                    )
                    yield status
    
    def _resample_audio(self) -> np.ndarray:
        """
        Resample audio from 24kHz to 16kHz
        
        Returns:
            Resampled audio at 16kHz
        """
        if len(self.source_buffer) == 0:
            return np.array([], dtype=np.int16)
        
        # Calculate target length for resampling
        target_length = len(self.source_buffer) * self.target_sample_rate // self.source_sample_rate
        
        if target_length == 0:
            return np.array([], dtype=np.int16)
        
        # Simple linear interpolation resampling
        source_indices = np.arange(len(self.source_buffer))
        target_indices = np.linspace(0, len(self.source_buffer) - 1, target_length)
        resampled = np.interp(target_indices, source_indices, self.source_buffer)
        
        # Keep some buffer for next iteration to avoid edge effects
        buffer_size = self.source_sample_rate // 10  # 100ms buffer at 24kHz
        if len(self.source_buffer) > buffer_size:
            self.source_buffer = self.source_buffer[-buffer_size:]
        else:
            self.source_buffer = np.array([], dtype=np.int16)
        
        return resampled.astype(np.int16)
    
    async def _detect_wake_word(self, audio_chunk: np.ndarray) -> Optional[dict]:
        """
        Run wake word detection on an audio chunk using openWakeWord
        
        Args:
            audio_chunk: Audio data at 16kHz (1280 samples)
            
        Returns:
            Detection result dict with scores and detection status
        """
        try:
            if self.oww_model is None:
                return None
            
            # Run prediction - similar to demo script
            prediction = self.oww_model.predict(audio_chunk)
            
            # Collect scores for all models
            current_scores = {}
            wake_word_detected = False
            detected_word = None
            max_confidence = 0.0
            
            # Check all models for detection (in case multiple models are loaded)
            for model_name in self.oww_model.prediction_buffer.keys():
                scores = list(self.oww_model.prediction_buffer[model_name])
                current_score = scores[-1]  # Get the latest prediction score
                current_scores[model_name] = float(current_score)
                
                if current_score > self.threshold:
                    wake_word_detected = True
                    if current_score > max_confidence:
                        max_confidence = current_score
                        detected_word = model_name
            
            # Always return scores, whether detected or not
            result = {
                'scores': current_scores,
                'detected': wake_word_detected
            }
            
            if wake_word_detected:
                result['wake_word'] = detected_word
                result['confidence'] = max_confidence
            
            return result
            
        except Exception as e:
            logger.error(f"[WAKE_WORD] Error during detection for client {self.client_id}: {e}")
            return None
    
    def _clear_buffers(self):
        """Clear audio buffers after wake word detection"""
        # Keep some small buffer to maintain context
        if len(self.target_buffer) > self.chunk_size // 2:
            self.target_buffer = self.target_buffer[-(self.chunk_size // 2):]
        else:
            self.target_buffer = np.array([], dtype=np.int16)
        
        # Clear source buffer more aggressively
        self.source_buffer = np.array([], dtype=np.int16)