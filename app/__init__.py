"""app 包入口

在这里加载一次 .env：任何 `import app.xxx` 都会先执行本文件，
从而保证 logger、各 config 模块读到的都是 .env 里的真实配置，
不需要每个模块各自 load_dotenv()。
"""
from app.config.env import load_env

load_env()
