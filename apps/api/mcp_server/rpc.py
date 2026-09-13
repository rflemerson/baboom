"""Serve the curation skill over MCP, beside the admin tools.

The instructions are one set of files under ``skills/``. This module
only adapts them to the JSON-RPC methods different clients ask for: the skills
extension where it is supported, resources for the files it points at, and
prompts for clients that speak only the stable specification.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from django.http import HttpResponse, JsonResponse
from django_admin_mcp_api.server import errors, jsonrpc

from mcp_server import loader

if TYPE_CHECKING:
    from django.http import HttpRequest

SKILLS_EXTENSION = "io.modelcontextprotocol/skills"
URI_SCHEME = "skill"
MARKDOWN = "text/markdown"


def _uri(slug: str, path: str) -> str:
    return f"{URI_SCHEME}://{slug}/{path}"


def _parse_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != URI_SCHEME or not parsed.netloc:
        msg = f"Not a skill URI: {uri!r}"
        raise loader.SkillError(msg)
    return parsed.netloc, unquote(parsed.path.lstrip("/")) or loader.SKILL_FILENAME


def _skill_entry(skill: loader.Skill) -> dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "uri": _uri(skill.slug, loader.SKILL_FILENAME),
        "frontmatter": {"name": skill.name, "description": skill.description},
        "digest": f"sha256:{skill.digest}",
        "resources": [_uri(skill.slug, path) for path in skill.files],
    }


def _contents(uri: str, text: str) -> dict[str, Any]:
    return {"contents": [{"uri": uri, "mimeType": MARKDOWN, "text": text}]}


def _read(uri: str) -> dict[str, Any]:
    slug, path = _parse_uri(uri)
    if path == loader.SKILL_FILENAME:
        return _contents(uri, loader.load(slug).body)
    return _contents(uri, loader.load_file(slug, path).text)


def _prompt_text(skill: loader.Skill) -> str:
    """Return the skill and everything it references as one document.

    A prompt is fetched once and cannot follow a URI, so the references have
    to travel with it.
    """
    parts = [skill.body]
    parts.extend(
        f"\n\n## {path}\n\n{loader.load_file(skill.slug, path).text}"
        for path in skill.files
    )
    return "".join(parts)


def _skills_list(_params: dict[str, Any]) -> dict[str, Any]:
    return {"skills": [_skill_entry(loader.load(s)) for s in loader.available()]}


def _skills_get(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name") or params.get("uri")
    if not name:
        msg = "skills/get needs a name or uri"
        raise loader.SkillError(msg)
    slug = _parse_uri(name)[0] if "://" in name else name
    skill = loader.load(slug)
    return {"skill": _skill_entry(skill), "content": skill.body}


def _resources_list(_params: dict[str, Any]) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for slug in loader.available():
        skill = loader.load(slug)
        resources.append(
            {
                "uri": _uri(slug, loader.SKILL_FILENAME),
                "name": skill.name,
                "description": skill.description,
                "mimeType": MARKDOWN,
            },
        )
        resources.extend(
            {"uri": _uri(slug, path), "name": path, "mimeType": MARKDOWN}
            for path in skill.files
        )
    return {"resources": resources}


def _resources_read(params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not uri:
        msg = "resources/read needs a uri"
        raise loader.SkillError(msg)
    return _read(uri)


def _prompts_list(_params: dict[str, Any]) -> dict[str, Any]:
    prompts = []
    for slug in loader.available():
        skill = loader.load(slug)
        prompts.append(
            {"name": skill.slug, "description": skill.description, "arguments": []},
        )
    return {"prompts": prompts}


def _resources_templates_list(_params: dict[str, Any]) -> dict[str, Any]:
    """No template: every file this server offers has a fixed URI."""
    return {"resourceTemplates": []}


def _prompts_get(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not name:
        msg = "prompts/get needs a name"
        raise loader.SkillError(msg)
    skill = loader.load(name)
    return {
        "description": skill.description,
        "messages": [
            {"role": "user", "content": {"type": "text", "text": _prompt_text(skill)}},
        ],
    }


HANDLERS = {
    "resources/templates/list": _resources_templates_list,
    "skills/list": _skills_list,
    "skills/get": _skills_get,
    "resources/list": _resources_list,
    "resources/read": _resources_read,
    "prompts/list": _prompts_list,
    "prompts/get": _prompts_get,
}


def handle(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Answer one of the methods this module adds."""
    return HANDLERS[method](params)


def declare_capabilities(payload: dict[str, Any]) -> dict[str, Any]:
    """Add what this module serves to an ``initialize`` result."""
    capabilities = payload.setdefault("result", {}).setdefault("capabilities", {})
    capabilities.setdefault("extensions", {})[SKILLS_EXTENSION] = {}
    capabilities.setdefault("prompts", {"listChanged": False})
    capabilities.setdefault("resources", {"listChanged": False, "subscribe": False})
    return payload


class SkillMethodsMixin:
    """Answer the skill, resource and prompt methods; delegate the rest."""

    def post(self, request: HttpRequest) -> HttpResponse:
        """Intercept the added methods, and advertise them on initialize."""
        try:
            payload = json.loads(request.body.decode() or "null")
        except UnicodeDecodeError, json.JSONDecodeError, AttributeError:
            payload = None
        method = payload.get("method") if isinstance(payload, dict) else None

        if method in HANDLERS:
            rpc_id = payload.get("id")
            params = payload.get("params") or {}
            try:
                result = handle(method, params)
            except loader.SkillError as exc:
                return JsonResponse(
                    jsonrpc.failure(rpc_id, errors.INVALID_PARAMS, str(exc)),
                    status=400,
                )
            return JsonResponse(jsonrpc.success(rpc_id, result))

        return self._adapt(method, super().post(request))

    @staticmethod
    def _adapt(method: str | None, response: HttpResponse) -> HttpResponse:
        """Add what this module serves to what the library answered."""
        if response.status_code != HTTPStatus.OK:
            return response
        body = json.loads(response.content)
        if method == "initialize":
            return JsonResponse(declare_capabilities(body))
        return response
