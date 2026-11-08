# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_bool, get_str


# 定义MinIO对象存储服务配置（与LLMConfig风格一致，字段对应.env配置项）
@dataclass
class MinIOConfig:
    endpoint: str    # MinIO服务地址（含http/https和端口）
    access_key: str  # MinIO访问密钥（对应MINIO_ACCESS_KEY）
    secret_key: str  # MinIO秘钥（对应MINIO_SECRET_KEY）
    bucket_name: str # MinIO默认存储桶名（知识库文件专用）
    minio_img_dir: str #Minio存储图片的文件夹
    minio_secure: bool # 是否启用HTTPS（对应MINIO_SECURE，内网部署一般为False）


# 实例化MinIO配置对象，自动从.env读取配置并绑定
minio_config = MinIOConfig(
    endpoint=get_str("MINIO_ENDPOINT"),
    access_key=get_str("MINIO_ACCESS_KEY"),
    secret_key=get_str("MINIO_SECRET_KEY"),
    bucket_name=get_str("MINIO_BUCKET_NAME", "knowledge-base-files"),
    minio_img_dir=get_str("MINIO_IMG_DIR", "/upload-images"),
    # 字符串转布尔由 get_bool 统一处理（直接 bool("False") 会得到 True）
    minio_secure=get_bool("MINIO_SECURE", False),
)
