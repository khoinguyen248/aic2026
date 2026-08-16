# app/utils/helpers.py
import random
from bson import ObjectId
from transformers import XLMRobertaTokenizer
import faiss
import numpy as np
import json
import os
import torch
from google import genai
import gc

def generate_random_number_string(length=10):
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def serialize_doc(doc: dict):
    """Chuyển ObjectId thành string trong 1 document"""
    if not doc:
        return None
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, list):
            result[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
        else:
            result[k] = v
    return result


def get_beit3_tokenizer():
    tokenizer = XLMRobertaTokenizer("beit3.spm")
    return tokenizer

def augment_query(query, num=5, llm=None):
    response = llm.models.generate_content(model="gemini-2.5-flash-lite",
                                            contents=f"Bạn hãy vào vai là một chuyên gia tạo prompt cho Gemini, sinh thêm cho tôi {num} câu bằng tiếng Anh tương tự ngữ nghĩa của \"{query}\" cho mục đích tăng cường dữ liệu huấn luyện mô hình Deep Learning, trả về dạng một chuỗi các câu cách nhau bởi dấu #, no yapping")
    return response.text.split(" #")

def create_faiss_index(embedding_root, metadata_root, model='beit3', get_metadata=False):
    D = 1024 if model == 'beit3' else 768
    index = faiss.IndexFlatIP(D)
    embedding_path = os.path.join(embedding_root, model)
    
    if not os.path.isdir(embedding_path):
        raise ValueError(f"{embedding_path} not found")
    
    files = sorted(os.listdir(embedding_path))
    if len(files) == 0:
        # Sử dụng logging an toàn cho cả Flask và non-Flask
        try:
            from flask import current_app
            current_app.logger.warning(f"No embedding files in {embedding_path}")
        except (ImportError, RuntimeError):
            print(f"Warning: No embedding files in {embedding_path}")
    
    metadata = []
    
    for embedding_file in sorted(os.listdir(embedding_path)):
        try:
            with open(os.path.join(embedding_path, embedding_file), 'rb') as f:
                embedding = np.load(f)
            index.add(embedding)
            
            if get_metadata:
                metadata_file = os.path.join(metadata_root, embedding_file.replace('.npy', '.json'))
                if os.path.exists(metadata_file):
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata.extend(json.load(f))
                else:
                    # Log warning an toàn
                    try:
                        from flask import current_app
                        current_app.logger.warning(f"Metadata file not found: {metadata_file}")
                    except (ImportError, RuntimeError):
                        print(f"Warning: Metadata file not found: {metadata_file}")
                        
        except Exception as e:
            # Xử lý lỗi an toàn cho cả Flask và non-Flask
            error_msg = f"Error processing file {embedding_file}: {str(e)}"
            try:
                from flask import current_app
                current_app.logger.error(error_msg)
            except (ImportError, RuntimeError):
                print(f"Error: {error_msg}")
            continue

    return index, metadata

def topk_fusion(sims, ids):
	N, k = np.shape(sims)
	sims = np.pad(sims, ((0,0),(0,1)))

	top_k_idx, top_k_sim = [], []
	hadIdx = set()
	cols = np.zeros(shape=(N, ), dtype=np.int32)
	while (len(hadIdx) < k):
		row = np.argmax(sims[np.arange(N), cols])
		if int(ids[row,cols[row]]) not in hadIdx:
			hadIdx.add(int(ids[row, cols[row]]))

			top_k_idx.append(int(ids[row, cols[row]]))
			top_k_sim.append(float(sims[row, cols[row]]))
			if cols[row] < k:
				cols[row] += 1
		else:
			cols[row] += 1

	return list(top_k_idx), top_k_sim

def faiss_search_results(query, index, k, augment=True, model=None, device='cpu',llm=None):
	agumented_queries = [query]
	if augment == True:
		agumented_queries = augment_query(query, 5, llm)

	
	queries_embedding = None
	with torch.inference_mode():
		if len(model) == 2:
			beit3, tokenizer = model
			t = tokenizer(agumented_queries, padding=True, return_tensors='pt')
			tokenized_queries = t['input_ids'].to(device)
			attention_mask = (1-t['attention_mask']).bool().to(device)
			beit3 = beit3.to(device)
			beit3.eval()
			_, queries_embedding = beit3(image=None,
										text_description=tokenized_queries,
										padding_mask=attention_mask,
										only_infer=True)
		else:
			clip, tokenizer, preprocess = model
			clip = clip.to(device)
			clip.eval()
			text = tokenizer(agumented_queries).to(device)
			queries_embedding = clip.encode_text(text)



	queries_embedding = queries_embedding.cpu().detach().numpy()

	faiss.normalize_L2(queries_embedding)

	sims, ids = index.search(queries_embedding, k=k)

	return sims, ids