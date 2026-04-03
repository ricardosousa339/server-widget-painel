import asyncio
from app.dependencies import widget_manager

async def test():
    widget_manager.update_config(enabled_widgets=["spotify","custom_gif","clock"], display_mode="hybrid", hybrid_period_seconds=100, hybrid_show_seconds=6)
    
    pl = await widget_manager.get_screen_payload()
    print("Payload widget:", pl["widget"])

asyncio.run(test())
