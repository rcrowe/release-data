import logging
from concurrent.futures import as_completed

from playwright.sync_api import sync_playwright
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError
from requests_cache import CachedSession
from requests_futures.sessions import FuturesSession
from urllib3.util import Retry

# See https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent.
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'


def fetch_urls(urls: list[str], data: any = None, headers: dict[str, str] = None,
               max_retries: int = 10, backoff_factor: float = 0.5, timeout: int = 30,
               cache: bool = False) -> list[Response]:
    logging.info(f"Fetching {urls}")

    try:
        underlying_session = CachedSession('/tmp/http_cache', backend='filesystem') if cache else None
        with FuturesSession(session=underlying_session) as session:
            adapter = HTTPAdapter(max_retries=Retry(total=max_retries, backoff_factor=backoff_factor))
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            headers = {'User-Agent': USER_AGENT} | ({} if headers is None else headers)
            futures = [session.get(url, headers=headers, data=data, timeout=timeout, stream=None) for url in urls]
            results = [future.result() for future in as_completed(futures)]

            logging.info(f"Fetched {urls}")
            return results
    except ChunkedEncodingError as e:  # See https://github.com/psf/requests/issues/4771#issue-354077499
        next_max_retries = max_retries - 1
        if next_max_retries == 0:
            logging.error(f"Got ChunkedEncodingError while fetching {urls} ({e}), giving up")
            raise e  # So that the function does not get stuck in an infinite loop.

        # We could wait a bit before retrying, but it's not clear if it would help.
        logging.warning(f"Got ChunkedEncodingError while fetching {urls} ({e}), retrying (remaining retries = {next_max_retries}).")
        return fetch_urls(urls, data, headers, next_max_retries, backoff_factor, timeout)


def fetch_url(url: str, data: any = None, headers: dict[str, str] = None,
              max_retries: int = 10, backoff_factor: float = 0.5, timeout: int = 30) -> Response:
    return fetch_urls([url], data, headers, max_retries, backoff_factor, timeout)[0]


# This requires some setup, see https://playwright.dev/python/docs/intro#installing-playwright.
def fetch_javascript_url(url: str) -> str:
    logging.info(f"Fetching {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, wait_until='networkidle')
            logging.info(f"Fetched {url}")
            return page.content()
        finally:
            browser.close()
