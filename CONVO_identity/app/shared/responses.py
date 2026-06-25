from typing import Any

from flask import jsonify


def api_response(
    *,
    success: bool,
    message: str,
    status_code: int,
    data: Any = None,
    errors: Any = None,
):
    response_body = {
        "success": success,
        "message": message,
    }

    if data is not None:
        response_body["data"] = data

    if errors is not None:
        response_body["errors"] = errors

    return jsonify(response_body), status_code