"""Run exactly one billable Seedream validation generation with redacted output."""

import asyncio
import os

from clothes_model.modules.providers.domain import ProviderInvocation
from clothes_model.modules.providers.infrastructure.volcengine_ark import (
    ARK_ADAPTER_TYPE,
    ARK_BASE_URL,
    ARK_MODEL,
    VolcengineArkSeedreamAdapter,
)


async def main() -> None:
    api_key = os.environ.get("CLOTHES_MODEL_PHASE4_ARK_API_KEY")
    if not api_key:
        raise SystemExit("CLOTHES_MODEL_PHASE4_ARK_API_KEY is required")
    adapter = VolcengineArkSeedreamAdapter()
    try:
        await adapter.validate(
            ProviderInvocation(
                provider_id="credentialed-smoke",
                config_revision_id="credentialed-smoke-v1",
                adapter_type=ARK_ADAPTER_TYPE,
                endpoint=ARK_BASE_URL,
                model=ARK_MODEL,
                timeout_seconds=120,
                credential=api_key,
            )
        )
    finally:
        await adapter.close()
    print("Seedream credentialed smoke passed: generations=1 model=doubao-seedream-4-5-251128")


if __name__ == "__main__":
    asyncio.run(main())
