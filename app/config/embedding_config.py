# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_bool, get_str


# 定义Embedding配置（适配BGE-M3的所有配置，类名embedding_config）
@dataclass
class EmbeddingConfig:
    bge_m3_path: str  # 本地模型路径
    bge_m3: str       # 模型仓库标识
    bge_device: str   # 运行设备(cuda:0/cpu)
    bge_fp16: bool    # 是否开启半精度（1=True/0=False）


# 实例化配置对象，和原代码lm_config风格保持一致
embedding_config = EmbeddingConfig(
    bge_m3_path=get_str("BGE_M3_PATH"),
    bge_m3=get_str("BGE_M3", "BAAI/bge-m3"),
    bge_device=get_str("BGE_DEVICE", "cpu"),
    # .env 里的 1/0/true/false 统一由 get_bool 解析
    bge_fp16=get_bool("BGE_FP16", False),
)
