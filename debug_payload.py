import asyncio
from app.dependencies import widget_manager

async def test():
    conf = widget_manager.get_widgets_config()
    print("Enabled:", conf["enabled_widgets"])
    print("Mode:", conf["display_mode"])
    pl = await widget_manager.get_screen_payload()
    print("Payload widget:", pl["widget"])

asyncio.run(test())
