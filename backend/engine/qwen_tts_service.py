import asyncio
import logging
import math
import os
import struct
import threading
import uuid
import wave
from typing import Any, Dict, List, Optional

# Configure AMD ROCm / MIOpen environment for GPU acceleration and clean logging
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("MIOPEN_LOG_LEVEL", "3")
os.environ.setdefault("MIOPEN_FIND_MODE", "FAST")

from backend.core.config import settings
from backend.utils.path_security import ensure_within_data_dir, safe_data_path

logger = logging.getLogger(__name__)

SUPPORTED_QWEN_MODELS: Dict[str, Dict[str, Any]] = {
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice": {
        "id": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "name": "Qwen3-TTS 0.6B CustomVoice (Fast & Lightweight)",
        "size_label": "~1.2 GB",
        "is_default": True,
        "type": "custom_voice",
        "parameters": "0.6B",
    },
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice": {
        "id": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "name": "Qwen3-TTS 1.7B CustomVoice (High Fidelity)",
        "size_label": "~3.4 GB",
        "is_default": False,
        "type": "custom_voice",
        "parameters": "1.7B",
    },
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base": {
        "id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "name": "Qwen3-TTS 0.6B Base",
        "size_label": "~1.2 GB",
        "is_default": False,
        "type": "base",
        "parameters": "0.6B",
    },
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base": {
        "id": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "name": "Qwen3-TTS 1.7B Base",
        "size_label": "~3.4 GB",
        "is_default": False,
        "type": "base",
        "parameters": "1.7B",
    },
}

DEFAULT_QWEN_VOICES: List[Dict[str, str]] = [
    {"name": "Vivian", "gender": "Female", "description": "Bright, clear narration"},
    {"name": "Serena", "gender": "Female", "description": "Warm, calm storyteller"},
    {"name": "Uncle_Fu", "gender": "Male", "description": "Gravelly, wise elder"},
    {"name": "Dylan", "gender": "Male", "description": "Youthful, energetic"},
    {"name": "Eric", "gender": "Male", "description": "Deep, confident adventurer"},
    {"name": "Ryan", "gender": "Male", "description": "Balanced, crisp narrator"},
    {"name": "Aiden", "gender": "Male", "description": "Heroic, bold delivery"},
    {"name": "Ono_Anna", "gender": "Female", "description": "Expressive, melodic"},
    {"name": "Sohee", "gender": "Female", "description": "Gentle, soothing tone"},
]


def _model_to_folder_name(model_id: str) -> str:
    """Sanitizes model id into a directory name."""
    return model_id.replace("/", "--").replace(":", "_")


def _get_qwen_models_dir() -> str:
    """Returns local base directory for Qwen models."""
    path = safe_data_path("models", "qwen_tts")
    os.makedirs(path, exist_ok=True)
    return path


def _get_model_dir(model_id: str) -> str:
    """Returns local directory for a specific model."""
    folder = _model_to_folder_name(model_id)
    return os.path.join(_get_qwen_models_dir(), folder)


def _get_dir_size_bytes(dir_path: str) -> int:
    """Calculates total size of files inside directory."""
    if not os.path.isdir(dir_path):
        return 0
    total = 0
    for root, _, files in os.walk(dir_path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def _format_size_bytes(size_bytes: int) -> str:
    """Formats bytes to human readable string."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


class QwenTTSService:
    """
    Manages Qwen3-TTS local models, downloading via Hugging Face,
    in-memory caching, device placement, and audio synthesis.
    """

    _loaded_models: Dict[str, Any] = {}
    _load_states: Dict[str, str] = {}  # "not_loaded" | "loading" | "loaded" | "error"
    _load_errors: Dict[str, str] = {}
    _load_locks: Dict[str, threading.Lock] = {}

    _download_states: Dict[str, Dict[str, Any]] = {}
    _download_locks: Dict[str, threading.Lock] = {}

    @classmethod
    def get_supported_models(cls) -> List[Dict[str, Any]]:
        """Returns list of all supported Qwen3-TTS models with download statuses."""
        result = []
        for model_id, info in SUPPORTED_QWEN_MODELS.items():
            model_dir = _get_model_dir(model_id)
            is_downloaded = cls.is_model_downloaded(model_id)
            disk_size = _get_dir_size_bytes(model_dir) if is_downloaded else 0
            
            dl_state = cls._download_states.get(model_id, {})
            current_status = dl_state.get("status")
            if not current_status:
                current_status = "downloaded" if is_downloaded else "not_downloaded"

            load_state = cls._load_states.get(model_id, "not_loaded")

            result.append({
                "id": model_id,
                "name": info["name"],
                "size_label": info["size_label"],
                "is_default": info["is_default"],
                "type": info["type"],
                "parameters": info["parameters"],
                "is_downloaded": is_downloaded,
                "disk_size_bytes": disk_size,
                "disk_size_formatted": _format_size_bytes(disk_size),
                "download_status": current_status,
                "download_progress": dl_state.get("progress", 100.0 if is_downloaded else 0.0),
                "load_status": load_state,
                "local_dir": model_dir,
            })
        return result

    @classmethod
    def get_default_voices(cls) -> List[Dict[str, str]]:
        """Returns built-in speaker voices for CustomVoice models."""
        return list(DEFAULT_QWEN_VOICES)

    @classmethod
    def is_model_downloaded(cls, model_id: str) -> bool:
        """Checks if model files exist on disk."""
        model_dir = _get_model_dir(model_id)
        if not os.path.isdir(model_dir):
            return False
        # Verify essential model indicator files exist
        has_config = os.path.isfile(os.path.join(model_dir, "config.json")) or os.path.isfile(os.path.join(model_dir, "model.safetensors.index.json"))
        has_weights = any(
            f.endswith((".safetensors", ".bin", ".pt"))
            for f in os.listdir(model_dir)
        )
        return has_config or has_weights

    @classmethod
    def get_execution_device(cls) -> str:
        """Detects whether CUDA GPU is available or falls back to CPU."""
        try:
            import torch
            if torch.cuda.is_available():
                return f"cuda (GPU: {torch.cuda.get_device_name(0)})"
        except Exception:
            pass
        return "cpu (CPU Mode)"

    @classmethod
    def get_download_status(cls, model_id: str) -> Dict[str, Any]:
        """Returns the current download progress and status for a model."""
        if model_id not in cls._download_states:
            is_dl = cls.is_model_downloaded(model_id)
            return {
                "model_id": model_id,
                "status": "downloaded" if is_dl else "idle",
                "progress": 100.0 if is_dl else 0.0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "error": None,
            }
        return cls._download_states[model_id]

    @classmethod
    def start_download(cls, model_id: str) -> Dict[str, Any]:
        """Starts asynchronous download of the model weights."""
        if model_id not in SUPPORTED_QWEN_MODELS:
            raise ValueError(f"Model '{model_id}' is not in the list of supported Qwen3-TTS models.")

        if model_id not in cls._download_locks:
            cls._download_locks[model_id] = threading.Lock()

        with cls._download_locks[model_id]:
            existing_state = cls._download_states.get(model_id, {})
            if existing_state.get("status") == "downloading":
                return existing_state

            cls._download_states[model_id] = {
                "model_id": model_id,
                "status": "downloading",
                "progress": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "error": None,
            }

            thread = threading.Thread(
                target=cls._download_worker,
                args=(model_id,),
                daemon=True,
                name=f"QwenTTS-Downloader-{model_id}"
            )
            thread.start()

            return cls._download_states[model_id]

    @classmethod
    def _download_worker(cls, model_id: str) -> None:
        """Worker thread executing snapshot_download from Hugging Face."""
        target_dir = _get_model_dir(model_id)
        os.makedirs(target_dir, exist_ok=True)
        logger.info("[QwenTTS] Starting snapshot download for %s to %s", model_id, target_dir)

        try:
            from huggingface_hub import snapshot_download
            from tqdm.auto import tqdm

            class HFProgressCallback(tqdm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._model_id = model_id

                def update(self, n=1):
                    super().update(n)
                    try:
                        total = self.total or 0
                        current = self.n or 0
                        if total > 0:
                            pct = round(min(100.0, (current / total) * 100.0), 1)
                            QwenTTSService._download_states[model_id].update({
                                "status": "downloading",
                                "progress": pct,
                                "downloaded_bytes": current,
                                "total_bytes": total,
                            })
                    except Exception:
                        pass

            snapshot_download(
                repo_id=model_id,
                local_dir=target_dir,
                local_dir_use_symlinks=False,
                resume_download=True,
                tqdm_class=HFProgressCallback,
            )

            cls._download_states[model_id] = {
                "model_id": model_id,
                "status": "downloaded",
                "progress": 100.0,
                "downloaded_bytes": _get_dir_size_bytes(target_dir),
                "total_bytes": _get_dir_size_bytes(target_dir),
                "error": None,
            }
            logger.info("[QwenTTS] Successfully downloaded %s", model_id)

        except Exception as exc:
            logger.exception("[QwenTTS] Download failed for %s", model_id)
            cls._download_states[model_id] = {
                "model_id": model_id,
                "status": "error",
                "progress": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "error": str(exc),
            }

    @classmethod
    def get_load_status(cls, model_id: str) -> Dict[str, Any]:
        """Returns the in-memory load state of the model."""
        state = cls._load_states.get(model_id, "not_loaded")
        error = cls._load_errors.get(model_id)
        device = cls.get_execution_device()
        return {
            "model_id": model_id,
            "status": state,
            "error": error,
            "device": device,
            "is_ready": state == "loaded",
        }

    @classmethod
    def preload_model(cls, model_id: str) -> None:
        """Preloads model in background thread if not already loaded."""
        if model_id not in cls._load_locks:
            cls._load_locks[model_id] = threading.Lock()

        with cls._load_locks[model_id]:
            state = cls._load_states.get(model_id, "not_loaded")
            if state in {"loaded", "loading"}:
                return

            cls._load_states[model_id] = "loading"
            cls._load_errors.pop(model_id, None)

            thread = threading.Thread(
                target=cls._load_worker,
                args=(model_id,),
                daemon=True,
                name=f"QwenTTS-Loader-{model_id}"
            )
            thread.start()

    @classmethod
    def resolve_active_model_id(cls, candidate: Optional[str] = None) -> str:
        """Resolves valid Qwen model id, falling back to downloaded model if candidate is invalid."""
        if candidate and candidate.startswith("Qwen/"):
            return candidate
        for m_id in SUPPORTED_QWEN_MODELS:
            if cls.is_model_downloaded(m_id):
                return m_id
        return "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

    @classmethod
    def _load_worker(cls, model_id: str) -> None:
        """Loads model weights into memory/GPU."""
        model_dir = _get_model_dir(model_id)
        logger.info("[QwenTTS] Loading model into memory: %s from %s", model_id, model_dir)

        if not cls.is_model_downloaded(model_id):
            cls._load_states[model_id] = "error"
            cls._load_errors[model_id] = f"Model '{model_id}' is not downloaded yet. Please download it first."
            logger.error("[QwenTTS] Cannot load %s: files missing", model_id)
            return

        try:
            from qwen_tts import Qwen3TTSModel
            import torch

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            logger.info("[QwenTTS] Instantiating Qwen3TTSModel from %s (device=%s, dtype=%s)...", model_dir, device, dtype)
            model_instance = Qwen3TTSModel.from_pretrained(
                model_dir,
                device_map=device,
                dtype=dtype,
            )

            cls._loaded_models[model_id] = model_instance
            cls._load_states[model_id] = "loaded"
            logger.info("[QwenTTS] Model %s successfully loaded into memory", model_id)

        except Exception as exc:
            logger.exception("[QwenTTS] Failed to load model %s", model_id)
            cls._load_states[model_id] = "error"
            cls._load_errors[model_id] = str(exc)

    @classmethod
    async def generate_speech(
        cls,
        text: str,
        voice: str = "Vivian",
        model_id: str = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        speed: float = 1.0,
        output_filepath: Optional[str] = None,
        instruct: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Synthesizes text using Qwen3-TTS and saves to a WAV file.
        Returns the output file path.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for TTS synthesis.")

        model_id = cls.resolve_active_model_id(model_id)

        # Ensure model is ready
        if not cls.is_model_downloaded(model_id):
            raise RuntimeError(
                f"Qwen3-TTS model '{model_id}' is not downloaded. Please download it in Admin Speech Settings."
            )

        model_instance = cls._loaded_models.get(model_id)
        if cls._load_states.get(model_id) != "loaded" or not hasattr(model_instance, "generate_custom_voice"):
            cls._loaded_models.pop(model_id, None)
            cls._load_states[model_id] = "not_loaded"
            cls.preload_model(model_id)
            # Wait up to 120 seconds for loading to finish
            for _ in range(240):
                if cls._load_states.get(model_id) == "loaded":
                    model_instance = cls._loaded_models.get(model_id)
                    break
                if cls._load_states.get(model_id) == "error":
                    err = cls._load_errors.get(model_id, "Unknown load error")
                    raise RuntimeError(f"Failed to load Qwen3-TTS model: {err}")
                await asyncio.sleep(0.5)

        if not model_instance or not hasattr(model_instance, "generate_custom_voice"):
            raise RuntimeError(f"Qwen3-TTS model '{model_id}' could not be initialized or is missing generation methods.")

        if not output_filepath:
            output_filepath = os.path.join(
                _get_qwen_models_dir(), f"qwen_{uuid.uuid4().hex}.wav"
            )

        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

        # Execute synthesis in background thread to avoid blocking FastAPI event loop
        await asyncio.to_thread(
            cls._synthesize_sync,
            model_instance=model_instance,
            text=text,
            voice=voice,
            model_id=model_id,
            speed=speed,
            output_path=output_filepath,
            instruct=instruct,
        )

        return output_filepath

    @classmethod
    def _synthesize_sync(
        cls,
        model_instance: Any,
        text: str,
        voice: str,
        model_id: str,
        speed: float,
        output_path: str,
        instruct: Optional[str] = None,
    ) -> None:
        """Synchronous speech generation worker."""
        if not hasattr(model_instance, "generate_custom_voice") and not hasattr(model_instance, "generate"):
            raise RuntimeError(f"Model instance {type(model_instance)} does not support speech generation.")

        import numpy as np
        import soundfile as sf

        # Normalize speaker name against model's supported speakers
        raw_speaker = (voice or "Vivian").strip().lower().replace(" ", "_")
        speaker_arg = raw_speaker
        if hasattr(model_instance, "get_supported_speakers"):
            supported = [str(s).lower() for s in model_instance.get_supported_speakers()]
            if raw_speaker not in supported:
                # Find matching or fallback
                matched = next((s for s in supported if s in raw_speaker or raw_speaker in s), None)
                speaker_arg = matched if matched else ("vivian" if "vivian" in supported else supported[0])

        logger.info("[QwenTTS] Generating neural speech with speaker '%s' (instruct: %s) for text (%d chars)", speaker_arg, instruct, len(text))

        gen_kwargs: Dict[str, Any] = {}
        if instruct and instruct.strip():
            gen_kwargs["instruct"] = instruct.strip()

        try:
            if hasattr(model_instance, "generate_custom_voice"):
                wavs, sample_rate = model_instance.generate_custom_voice(
                    text=text,
                    speaker=speaker_arg,
                    language="Auto",
                    **gen_kwargs,
                )
            else:
                wavs, sample_rate = model_instance.generate(
                    text=text,
                    speaker=speaker_arg,
                    **gen_kwargs,
                )

            # Unpack list of waveforms
            audio_data = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            if hasattr(audio_data, "cpu"):
                audio_data = audio_data.cpu().numpy()
            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data)

            sf.write(output_path, audio_data, sample_rate)
            file_size = os.path.getsize(output_path)
            logger.info("[QwenTTS] Generated neural audio saved to %s (%d bytes, sample_rate=%d)", output_path, file_size, sample_rate)
        except Exception as e:
            logger.exception("[QwenTTS] Neural synthesis failed: %s", e)
            raise

