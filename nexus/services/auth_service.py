import httpx
from typing import Optional
from config.config import get_config
from config.logger import get_logger

settings = get_config()
logger = get_logger(__name__)

def check_login(auth_token: Optional[str] = None) -> bool:
    """
    校验登录状态。
    """
    url = f"{settings.FASTFLOW_API_URL}/fastflow/api/v1/auth/checkLogin"
    headers = {}
    if auth_token:
        headers["Authorization"] = auth_token

    try:
        # 使用 httpx 获取节点定义
        response = httpx.post(url, headers=headers, timeout=5.0)
        response.raise_for_status()
        
        response_data = response.json()
        if response_data.get("code") == 200 or response_data.get("code") == 0:
            return True
        else:
            logger.error(f"Check login failed: {response_data.get('message')}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking login: {e}")
        return False
