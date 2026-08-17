
from app.utils.helpers import * #tôi muốn thay thành from helpers import *
import numpy as np
import os
from pathlib import Path
import faiss
import torch
from PIL import Image
import torchvision
import torchvision.transforms as transforms
import json
from beit3.modeling_finetune import beit3_large_patch16_384_retrieval
from beit3 import *
import open_clip
from google import genai
from flask import current_app

def create_beit3():
    model = beit3_large_patch16_384_retrieval(pretrained=True)
    checkpoint_path = current_app.config.get("BEIT3_CHECKPOINT_PATH")
    model.load_state_dict(torch.load(checkpoint_path)['model'])

    tokenizer = get_beit3_tokenizer()

    return model, tokenizer

def create_clip():
    clip, _, preprocess = open_clip.create_model_and_transforms('ViT-L-14', pretrained='laion2B-s32B-b82K')
    clip.eval()  # model in train mode by default, impacts some models with BatchNorm or stochastic depth active
    tokenizer = open_clip.get_tokenizer('ViT-L-14')

    return clip, tokenizer, preprocess

def create_llm():
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        current_app.logger.warning("GEMINI_API_KEY chưa cấu hình -> bỏ qua HyDE/augment (LLM=None)")
        return None
    client = genai.Client(api_key=api_key)
    return client