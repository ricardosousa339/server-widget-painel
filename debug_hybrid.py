import asyncio, time
from app.dependencies import widget_manager

async def test():
    conf = widget_manager._display_config()
    print("conf:", conf)
    print("is_window:", widget_manager._is_hybrid_custom_window(conf))
    pl = await widget_manager._payload_for_widget("custom_gif", enabled_widgets={"custom_gif"}, image_mode="rgb565_base64")
    print("custom_payload:", pl["widget"] if pl else None)
    
if __name__ == "__main__":
    asyncio.run(test())
