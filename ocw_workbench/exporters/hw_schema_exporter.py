import yaml

def export_schema(data, path):
    with open(path, "w") as f:
        yaml.dump(data, f)