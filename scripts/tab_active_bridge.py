"""Adapt only Tab Info's playtime input and label; preserve all other resources."""
import io
import zipfile


def patch_tab_jar(original):
    source = io.BytesIO(original)
    result = io.BytesIO()
    changed = set()
    with zipfile.ZipFile(source) as jar, zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as output:
        for entry in jar.infolist():
            content = jar.read(entry.filename)
            if entry.filename == "data/tab_info/function/load.mcfunction":
                text = content.decode()
                old = "scoreboard objectives add playtime minecraft.custom:minecraft.play_time"
                new = "scoreboard objectives add hk.active_ticks dummy"
                if old not in text and new not in text:
                    raise ValueError("Unsupported Tab Info load function")
                text = text.replace(old, new)
                content = text.encode()
                changed.add("load")
            elif entry.filename == "data/tab_info/function/display/playtime/main.mcfunction":
                text = content.decode()
                old = "scoreboard players operation @s playtime_hours = @s playtime"
                new = "scoreboard players operation @s playtime_hours = @s hk.active_ticks"
                if old not in text and new not in text:
                    raise ValueError("Unsupported Tab Info playtime function")
                content = text.replace(old, new).encode()
                changed.add("display")
            elif entry.filename.endswith("/tab_info/function/display/playtime/template.mcfunction"):
                content = content.replace(b'"Playtime"', b'"Aktiv"')
            output.writestr(entry, content)
    if changed != {"load", "display"}:
        raise ValueError("Required Tab Info functions not found")
    return result.getvalue()
