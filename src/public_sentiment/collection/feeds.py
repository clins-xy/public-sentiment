import ipaddress
import socket
import urllib.request
import xml.etree.ElementTree as ElementTree
from urllib.parse import urlsplit

from ..core.sources import normalize_source, plain_text

def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("只允许公开 HTTP(S) RSS 地址")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("禁止采集内网、环回或保留地址")


class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        validate_public_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def read_feed(feed: dict, timeout: int) -> list:
    validate_public_url(feed["url"])
    request = urllib.request.Request(feed["url"], headers={"User-Agent": "PublicSentiment/0.1 RSS reader"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        content = response.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("RSS 超过 2 MiB 限制")
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("不接受包含 DTD 的 XML")
    root = ElementTree.fromstring(content)
    entries = root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry")
    sources = []
    for index, entry in enumerate(entries[:500]):
        values = {}
        for child in entry:
            tag = child.tag.rsplit("}", 1)[-1]
            values[tag] = "".join(child.itertext())
            if tag == "link" and child.get("href") and child.get("rel", "alternate") == "alternate":
                values["link"] = child.get("href")
        title = plain_text(values.get("title", "无标题"))
        description = plain_text(values.get("description") or values.get("summary") or values.get("content") or title)
        sources.append(normalize_source({
            "title": title, "content": description, "url": values.get("link", feed["url"]),
            "source_type": feed["source_type"], "published_at": values.get("pubDate") or values.get("published") or values.get("updated", ""),
            "author": values.get("author") or values.get("creator") or urlsplit(feed["url"]).hostname,
        }, index))
    return sources
