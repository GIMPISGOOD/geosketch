from llama_cpp import Llama
llm = Llama(model_path="models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", n_ctx=512, verbose=False)
print("模型加载成功！")