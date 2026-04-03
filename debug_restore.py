import asyncio
from app.dependencies import widget_manager

async def test():
    widget_manager.update_config(enabled_widgets=["spotify","custom_gif","vertical_image","clock"], display_mode="hybrid", hybrid_period_seconds=100, hybrid_show_seconds=6)

asyncio.run(test())
