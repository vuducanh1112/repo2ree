import requests
import json

import logging

logging.basicConfig(level=logging.INFO)


def generate_completion(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    format: str,
) -> str:
    """Generate a completion from the language model. Based on ollama api specification."""

    headers = {
        # "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "format": format,
        # "stream": True,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses

        full_response: list[dict] = []

        for line in response.iter_lines():
            if line:
                full_response.append(json.loads(line))

        response_text = ""
        for response_chunk in full_response:
            response_text += response_chunk.get("response", "")

        return response_text
    except requests.HTTPError as e:
        logging.error(f"HTTP error occurred: {e}")
        return ""
    except requests.RequestException as e:
        logging.error(f"Error generating completion: {e}")
        return ""


if __name__ == "__main__":
    from pathlib import Path

    url = "http://host.docker.internal:11434/api/generate"
    api_key = ""
    model = "deepseek-r1"
    readme_content = (
        Path("./")
        / "experiments"
        / "subjects"
        / "icse"
        / "2020"
        / "OpenVocabCodeNLM"
        / "README.md"
    ).read_text()
    prompt = f"""

    Extract the declared Python version and list of dependencies from the following README content.

    --- README CONTENT START ---
    {readme_content}
    --- README CONTENT END ---

    Respond in the following JSON format:
    {{
        "python_version": "<version_or_None>",
        "dependencies": ["<dependency1>", "<dependency2>", ...]
    }}
"""

    format = "json"
    completion = generate_completion(
        url=url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        format=format,
    )

    print(completion)
