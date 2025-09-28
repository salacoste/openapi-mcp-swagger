#!/usr/bin/env python3
"""
Standalone MCP Server for Cursor/Claude Code
Запускается без внешних зависимостей
"""

import json
import sys
import os
from typing import Dict, Any, List
from pathlib import Path


class StandaloneMCPServer:
    def __init__(self, swagger_file: str):
        self.swagger_file = Path(swagger_file)
        self.swagger_data = self._load_swagger()

    def _load_swagger(self) -> Dict[str, Any]:
        """Загрузка Swagger файла"""
        try:
            with open(self.swagger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to load swagger file: {e}"}

    def search_endpoints(
        self, keywords: str, http_methods: List[str] = None, max_results: int = 10
    ) -> Dict[str, Any]:
        """Поиск endpoints по ключевым словам"""
        if "error" in self.swagger_data:
            return self.swagger_data

        results = []
        paths = self.swagger_data.get("paths", {})

        keywords_lower = keywords.lower()

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() == "PARAMETERS":
                    continue

                if http_methods and method.upper() not in [
                    m.upper() for m in http_methods
                ]:
                    continue

                # Поиск в summary, description, tags
                summary = details.get("summary", "").lower()
                description = details.get("description", "").lower()
                tags = " ".join(details.get("tags", [])).lower()

                if (
                    keywords_lower in summary
                    or keywords_lower in description
                    or keywords_lower in tags
                    or keywords_lower in path.lower()
                ):
                    results.append(
                        {
                            "endpoint_id": f"{method}_{path.replace('/', '_')}",
                            "path": path,
                            "method": method.upper(),
                            "summary": details.get("summary", ""),
                            "description": details.get("description", ""),
                            "tags": details.get("tags", []),
                        }
                    )

                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        return {"results": results, "total": len(results), "query": keywords}

    def get_schema(self, component_name: str, max_depth: int = 3) -> Dict[str, Any]:
        """Получение схемы компонента"""
        if "error" in self.swagger_data:
            return self.swagger_data

        components = self.swagger_data.get("components", {})
        schemas = components.get("schemas", {})

        if component_name in schemas:
            return {
                "component_name": component_name,
                "schema": schemas[component_name],
                "type": "schema",
            }

        # Поиск по частичному совпадению
        matches = []
        for name, schema in schemas.items():
            if component_name.lower() in name.lower():
                matches.append({"name": name, "schema": schema})

        if matches:
            return {
                "component_name": component_name,
                "matches": matches,
                "type": "partial_match",
            }

        return {
            "error": f"Component '{component_name}' not found",
            "available_components": list(schemas.keys()),
        }

    def get_example(
        self, endpoint_id: str, language: str = "javascript", style: str = "production"
    ) -> Dict[str, Any]:
        """Генерация примера запроса"""
        # Упрощенная генерация примеров
        examples = {
            "javascript": {
                "auth": """
async function getOzonAuthToken(clientId, clientSecret) {
  const response = await fetch('https://api-performance.ozon.ru/api/client/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: 'client_credentials'
    })
  });

  return await response.json();
}""",
                "campaign": """
async function createCampaign(accessToken, campaignData) {
  const response = await fetch('https://api-performance.ozon.ru/api/client/campaign', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify(campaignData)
  });

  return await response.json();
}""",
            },
            "python": {
                "auth": """
import requests

def get_ozon_auth_token(client_id: str, client_secret: str) -> dict:
    url = "https://api-performance.ozon.ru/api/client/token"

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, json=payload)
    return response.json()""",
                "campaign": """
def create_campaign(access_token: str, campaign_data: dict) -> dict:
    url = "https://api-performance.ozon.ru/api/client/campaign"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.post(url, json=campaign_data, headers=headers)
    return response.json()""",
            },
        }

        # Определяем тип примера по endpoint_id
        if "token" in endpoint_id.lower() or "auth" in endpoint_id.lower():
            example_type = "auth"
        elif "campaign" in endpoint_id.lower():
            example_type = "campaign"
        else:
            example_type = "auth"  # По умолчанию

        return {
            "endpoint_id": endpoint_id,
            "language": language,
            "style": style,
            "example": examples.get(language, {}).get(
                example_type, "# Example not available for this combination"
            ),
        }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка MCP запроса"""
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "searchEndpoints":
            return self.search_endpoints(
                keywords=params.get("keywords", ""),
                http_methods=params.get("httpMethods"),
                max_results=params.get("maxResults", 10),
            )
        elif method == "getSchema":
            return self.get_schema(
                component_name=params.get("componentName", ""),
                max_depth=params.get("maxDepth", 3),
            )
        elif method == "getExample":
            return self.get_example(
                endpoint_id=params.get("endpointId", ""),
                language=params.get("language", "javascript"),
                style=params.get("style", "production"),
            )
        else:
            return {"error": f"Unknown method: {method}"}


def main():
    """Основная функция для CLI использования"""
    if len(sys.argv) < 2:
        print("Usage: standalone-mcp.py <swagger-file.json>")
        sys.exit(1)

    swagger_file = sys.argv[1]
    server = StandaloneMCPServer(swagger_file)

    # Режим STDIO для MCP
    if "--stdio" in sys.argv:
        # Чтение JSON-RPC запросов из stdin
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = server.handle_request(request)
                print(json.dumps(response))
                sys.stdout.flush()
            except Exception as e:
                error_response = {"error": str(e), "code": -32000}
                print(json.dumps(error_response))
                sys.stdout.flush()
    else:
        # Интерактивный режим для тестирования
        print("🚀 Standalone MCP Server started")
        print("Available methods: searchEndpoints, getSchema, getExample")
        print("Type 'quit' to exit\n")

        while True:
            try:
                user_input = input("Enter method and params (JSON): ").strip()
                if user_input.lower() == "quit":
                    break

                request = json.loads(user_input)
                response = server.handle_request(request)
                print(json.dumps(response, indent=2, ensure_ascii=False))
                print()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()
