import asyncio

from openai_codex import AsyncCodex
from flow.codex_llm import _config, _preflight


async def login():
    async with AsyncCodex(_config()) as codex:
        handle = await codex.login_chatgpt_device_code()
        print(handle.verification_url, flush=True)
        print(handle.user_code, flush=True)
        result = await handle.wait()
        if not result.success:
            raise RuntimeError(result.error or 'Subscription login failed')
        await _preflight(codex, 'gpt-5.6-sol')
        print('ChatGPT subscription and Sol availability verified', flush=True)


if __name__ == '__main__':
    asyncio.run(login())
