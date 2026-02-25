"""Example plugin tools."""
import json


class DataFormatTool:
    name = "data_format"
    description = "Convert data between formats (JSON, CSV, YAML)"
    category = "data"

    async def execute(self, params, agent=None):
        data = params.get("data", "")
        from_fmt = params.get("from", "json")
        to_fmt = params.get("to", "csv")

        if from_fmt == "json" and to_fmt == "csv":
            try:
                rows = json.loads(data)
                if isinstance(rows, list) and rows:
                    headers = list(rows[0].keys())
                    lines = [",".join(headers)]
                    for row in rows:
                        lines.append(",".join(str(row.get(h, "")) for h in headers))
                    return "\n".join(lines)
            except Exception as e:
                return f"Error: {e}"
        return f"Conversion {from_fmt} -> {to_fmt} not supported"
