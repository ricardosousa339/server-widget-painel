import asyncio
from app.dependencies import widget_manager

async def test():
    conf = widget_manager.get_widgets_config()
    enabled = set(conf["enabled_widgets"])
    if "vertical_image" in enabled:
        enabled.remove("vertical_image")
    widget_manager.update_config(enabled_widgets=list(enabled))
    print("Vertical image disabled. Enabled widgets:", enabled)

asyncio.run(test())
