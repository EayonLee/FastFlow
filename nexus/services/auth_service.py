import httpx
from typing import Optional
from nexus.config.config import get_config
from nexus.config.logger import get_logger

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
    else:
        logger.warning("Check login without Authorization, Skip check.")
        return False

    try:
        # 使用 httpx 校验登录状态，显式禁用代理（避免 VPN/系统代理干扰本地请求）
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                url,
                headers=headers,
                timeout=5.0,
                follow_redirects=True,
            )
        response.raise_for_status()
        
        response_data = response.json()
        if response_data.get("code") == 200 or response_data.get("code") == 0:
            return True
        else:
            logger.error(f"Check login failed: {response_data.get('message')}")
            return False
            
    except httpx.HTTPStatusError as e:
        logger.error(
            "Check login failed with status=%s  body=%s headers=%s",
            e.response.status_code,
            e.response.text,
            dict(e.response.headers),
        )
        return False
    except Exception as e:
        logger.error(f"Error checking login: {e}")
        return False
