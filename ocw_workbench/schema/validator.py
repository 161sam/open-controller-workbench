def validate_schema(data: dict):
    if "controller" not in data:
        raise ValueError("Missing controller section")