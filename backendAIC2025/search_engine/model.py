from __future__ import annotations

from collections import OrderedDict
import gc
import sys
import threading
from pathlib import Path
import numpy as np
import sentencepiece as spm
import torch
import torchvision.transforms as T
from PIL import Image
from transformers import AutoModel, AutoProcessor

try:
    from .config import SearchConfig, DEFAULT_CONFIG
    from .utils import l2_normalize, load_image, normalize_model_name
except ImportError:  # Allow `python model.py` from this directory.
    from config import SearchConfig, DEFAULT_CONFIG
    from utils import l2_normalize, load_image, normalize_model_name


class BaseEncoder:
    vector_size: int

    def encode_text(self, text: str) -> np.ndarray:
        raise NotImplementedError

    def encode_image(self, image: str | Path | Image.Image) -> np.ndarray:
        raise NotImplementedError


class BEIT3SentencePieceTokenizer:
    """Minimal XLM-R tokenizer compatible with the original BEiT-3 vocab."""

    cls_token_id = 0
    pad_token_id = 1
    sep_token_id = 2
    unk_token_id = 3

    def __init__(self, model_path: Path):
        self.sp_model = spm.SentencePieceProcessor(model_file=str(model_path))

    def _encode(self, text: str, max_length: int) -> list[int]:
        pieces = self.sp_model.encode(text, out_type=str)
        token_ids = []
        for piece in pieces:
            piece_id = self.sp_model.piece_to_id(piece)
            token_ids.append(piece_id + 1 if piece_id else self.unk_token_id)

        input_ids = [self.cls_token_id, *token_ids, self.sep_token_id]
        if len(input_ids) > max_length:
            input_ids = input_ids[:max_length]
            input_ids[-1] = self.sep_token_id
        return input_ids

    def __call__(
        self,
        texts: list[str],
        *,
        padding: bool = True,
        truncation: bool = True,
        max_length: int = 100,
        return_tensors: str = "pt",
    ) -> dict[str, torch.Tensor]:
        if return_tensors != "pt":
            raise ValueError("BEiT-3 tokenizer only supports return_tensors='pt'")

        effective_max_length = max_length if truncation else 2**31 - 1
        encoded = [self._encode(text, effective_max_length) for text in texts]
        target_length = max(len(ids) for ids in encoded) if padding else None

        input_ids = []
        attention_mask = []
        for ids in encoded:
            pad_count = (target_length - len(ids)) if target_length is not None else 0
            input_ids.append(ids + [self.pad_token_id] * pad_count)
            attention_mask.append([1] * len(ids) + [0] * pad_count)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
        }


class BEIT3Encoder(BaseEncoder):
    vector_size = 1024

    def __init__(self, config: SearchConfig):
        self.config = config
        self.device = torch.device(config.device if torch.cuda.is_available() or config.device == "cpu" else "cpu")
        beit3_dir = config.base_dir / "beit3"
        previous_utils = sys.modules.pop("utils", None)
        sys.path.insert(0, str(beit3_dir))
        try:
            from modeling_finetune import beit3_large_patch16_384_retrieval
            from utils import load_model_and_may_interpolate
        finally:
            if sys.path[0] == str(beit3_dir):
                sys.path.pop(0)
            if previous_utils is not None:
                sys.modules["utils"] = previous_utils

        self.model = beit3_large_patch16_384_retrieval(pretrained=True)
        load_model_and_may_interpolate(
            str(config.beit3_checkpoint),
            self.model,
            model_key="model|module",
            model_prefix="",
        )
        self.model.to(self.device).eval()
        self.tokenizer = BEIT3SentencePieceTokenizer(config.beit3_spm)
        self.image_transform = T.Compose(
            [
                T.Resize((384, 384), interpolation=T.InterpolationMode.BICUBIC),
                T.ToTensor(),
                T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ]
        )

    def encode_text(self, text: str) -> np.ndarray:
        tokens = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=100,
            return_tensors="pt",
        )
        with torch.inference_mode():
            _, text_embedding = self.model(
                image=None,
                text_description=tokens["input_ids"].to(self.device),
                padding_mask=(1 - tokens["attention_mask"]).bool().to(self.device),
                only_infer=True,
            )
        return l2_normalize(text_embedding[0].detach().cpu().numpy().astype(np.float32))

    def encode_image(self, image: str | Path | Image.Image) -> np.ndarray:
        img = load_image(image)
        tensor = self.image_transform(img).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            image_embedding, _ = self.model(image=tensor, text_description=None, padding_mask=None, only_infer=True)
        return l2_normalize(image_embedding[0].detach().cpu().numpy().astype(np.float32))


class JinaOmniEncoder(BaseEncoder):
    vector_size = 1024

    def __init__(self, model_name: str, config: SearchConfig):
        self.model_name = model_name
        self.device = torch.device(config.device if torch.cuda.is_available() or config.device == "cpu" else "cpu")
        self.processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            default_task="retrieval",
            modality="vision",
        )
        self.model.to(self.device).eval()

    def encode_text(self, text: str) -> np.ndarray:
        with torch.inference_mode():
            inputs = self.processor(text=f"Query: {text}", return_tensors="pt").to(self.device)
            output = self.model.embed(**inputs).to(torch.float32)
            print(output)
        return l2_normalize(output[0].detach().cpu().numpy())

    def encode_image(self, image: str | Path | Image.Image) -> np.ndarray:
        img = load_image(image)
        with torch.inference_mode():
            inputs = self.processor(
                images=img,
                text="Query: <|vision_start|><|image_pad|><|vision_end|>",
                truncation=False,
                return_tensors="pt",
            ).to(self.device)
            output = self.model.embed(**inputs).to(torch.float32)
        return l2_normalize(output[0].detach().cpu().numpy())


class OpenCLIPEncoder(BaseEncoder):
    def __init__(self, model_name: str, vector_size: int, config: SearchConfig):
        import open_clip

        self.model_name = model_name
        self.vector_size = vector_size
        self.device = torch.device(config.device if torch.cuda.is_available() or config.device == "cpu" else "cpu")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name)
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.to(self.device).eval()

    def encode_text(self, text: str) -> np.ndarray:
        context_length = getattr(self.model, "context_length", 77)
        tokens = self.tokenizer([text], context_length=context_length).to(self.device)
        with torch.inference_mode():
            output = self.model.encode_text(tokens, normalize=True).to(torch.float32)
        return l2_normalize(output[0].detach().cpu().numpy())

    def encode_image(self, image: str | Path | Image.Image) -> np.ndarray:
        tensor = self.preprocess(load_image(image)).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            output = self.model.encode_image(tensor, normalize=True).to(torch.float32)
        return l2_normalize(output.detach().cpu().numpy())


class ModelRegistry:
    def __init__(self, config: SearchConfig = DEFAULT_CONFIG):
        self.config = config
        self._encoders: OrderedDict[str, BaseEncoder] = OrderedDict()
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _create_encoder(self, name: str) -> BaseEncoder:
        if name == "beit3":
            return BEIT3Encoder(self.config)
        if name == "jina":
            return JinaOmniEncoder(
                self.config.jina_model_name,
                self.config,
            )
        return OpenCLIPEncoder(
            self.config.pe_model_name,
            self.config.models[name].vector_size,
            self.config,
        )

    def _evict_if_needed(self) -> None:
        while len(self._encoders) >= self.config.model_cache_size:
            _, encoder = self._encoders.popitem(last=False)
            del encoder
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def get(self, model: str) -> BaseEncoder:
        name = normalize_model_name(model)
        with self._load_lock:
            encoder = self._encoders.get(name)
            if encoder is not None:
                self._encoders.move_to_end(name)
                return encoder

            self._evict_if_needed()
            encoder = self._create_encoder(name)
            self._encoders[name] = encoder
            return encoder

    def encode_text(self, text: str, model: str = "beit3") -> np.ndarray:
        encoder = self.get(model)
        with self._inference_lock:
            return encoder.encode_text(text)

    def encode_image(self, image: str | Path | Image.Image, model: str = "beit3") -> np.ndarray:
        encoder = self.get(model)
        with self._inference_lock:
            return encoder.encode_image(image)
