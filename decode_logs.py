#!/usr/bin/env python3
"""Script to decode OTLP protobuf logs to JSON"""

import base64
import json
import sys
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest


def decode_protobuf_logs(base64_data: str) -> str:
    """Decode base64 encoded protobuf logs to JSON"""
    # Decode base64 to bytes
    protobuf_bytes = base64.b64decode(base64_data)

    # Parse protobuf
    request = ExportLogsServiceRequest()
    request.ParseFromString(protobuf_bytes)

    # Convert to dict/JSON
    def message_to_dict(message):
        """Convert protobuf message to dict"""
        result = {}
        for field in message.DESCRIPTOR.fields:
            value = getattr(message, field.name)
            if field.type == field.TYPE_MESSAGE:
                if field.label == field.LABEL_REPEATED:
                    result[field.name] = [message_to_dict(item) for item in value]
                else:
                    result[field.name] = message_to_dict(value)
            elif field.label == field.LABEL_REPEATED:
                result[field.name] = list(value)
            else:
                if isinstance(value, bytes):
                    result[field.name] = value.decode("utf-8", errors="replace")
                else:
                    result[field.name] = value
        return result

    logs_dict = message_to_dict(request)
    return json.dumps(logs_dict, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python decode_logs.py <base64_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    with open(file_path, "r", encoding="utf-8") as f:
        base64_data = f.read().strip()

    try:
        json_output = decode_protobuf_logs(base64_data)
        print(json_output)
    except (ValueError, base64.binascii.Error) as e:
        print(f"Error decoding: {e}", file=sys.stderr)
        sys.exit(1)
