import asyncio
import os
import traceback

import openai


async def main():
    print("openai version:", openai.__version__)
    print("OPENAI_BASE_URL:", os.getenv("OPENAI_BASE_URL"))
    print("HTTPS_PROXY:", bool(os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")))
    print("HTTP_PROXY:", bool(os.getenv("HTTP_PROXY") or os.getenv("http_proxy")))
    print("ALL_PROXY:", bool(os.getenv("ALL_PROXY") or os.getenv("all_proxy")))
    print("SSL_CERT_FILE:", os.getenv("SSL_CERT_FILE"))
    print("REQUESTS_CA_BUNDLE:", os.getenv("REQUESTS_CA_BUNDLE"))

    api_key = os.getenv("OPENAI_API_KEY", "dummy")
    client = openai.AsyncOpenAI(
        api_key=api_key,
        max_retries=0,
        timeout=10.0,
    )

    try:
        result = await client.models.list()
        print("\nSUCCESS: models endpoint reached")
        print("models returned:", len(result.data))
    except openai.APIConnectionError as exc:
        print("\nAPIConnectionError:", repr(exc))
        print("direct cause:", repr(exc.__cause__))

        cause = exc.__cause__
        depth = 0
        while cause is not None:
            print(f"cause[{depth}]: {type(cause).__name__}: {cause!r}")
            cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
            depth += 1

        print("\nTRACEBACK:")
        traceback.print_exception(exc)
    except Exception as exc:
        print("\n" + type(exc).__name__, repr(exc))
        traceback.print_exception(exc)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
