import asyncio
from app.dependencies import widget_manager

async def test():
    widget_manager.update_config(enabled_widgets=["clock"])
    
    pl = await widget_manager.get_screen_payload()
    print("Payload widget:", pl["widget"])
    if pl["widget"] == "clock":
        print(pl["data"])

asyncio.run(test())
