from typing import Optional
import aiohttp
import config


class CaptchaSolver:
    def __init__(self):
        self.solve_url = config.CAPTCHA_SOLVER_HOST + '/math-captcha/solve'

    async def solve(self, captcha_svg: str) -> Optional[str]:
        data = {"data": captcha_svg}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.solve_url, json=data) as response:
                    if response.status != 200:
                        return None
                    else:
                        data = await response.json()
                        return str(data["data"])
        except Exception:
            return None
