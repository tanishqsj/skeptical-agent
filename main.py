import chainlit as cl
from langchain_core.messages import HumanMessage
from agents.workflow import app
from agents.tools import upload_to_sandbox

@cl.on_chat_start
async def start():
    cl.user_session.set("id", cl.user_session.get("id", "default_thread"))
    await cl.Message(
        content="👥 **Swarm Active:** Manager, Coder, and Skeptic are ready.\n\nUpload a dataset to begin!",
        author="System"
    ).send()

@cl.on_message
async def handle_message(message: cl.Message):
    user_text = message.content
    
    # 1. Handle File Uploads
    if message.elements:
        for element in message.elements:
            if element.path:
                remote_path = element.name 
                upload_to_sandbox(element.path, remote_path)
                user_text += f"\n\n[SYSTEM: File '{remote_path}' uploaded.]"
                await cl.Message(content=f"📂 Uploaded {element.name}", author="System").send()

    # 2. Run the Swarm
    inputs = {"messages": [HumanMessage(content=user_text)], "sender": "user"}
    config = {"configurable": {"thread_id": cl.user_session.get("id")}}

    # --- THE FIX ---
    # We add 'recursion_limit': 50 (Double the default of 25)
    config = {
        "configurable": {"thread_id": cl.user_session.get("id")},
        "recursion_limit": 50 
    }
    
    async for output in app.astream(inputs, config=config, stream_mode="values"):
        last_message = output["messages"][-1]
        
        # Skip tool calls
        if getattr(last_message, "tool_calls", None):
            continue
            
        # Determine Author Name based on the content or custom logic
        # In a real app, we'd pass the 'sender' field from the state properly.
        # For now, we infer it or just label it 'Agent Team'.
        
        author_name = "Agent Team"
        # We can try to guess who is speaking based on the prompts
        if "Manager" in str(output.get("sender", "")): author_name = "Manager"
        
        if last_message.type == "ai":
            await cl.Message(
                content=last_message.content,
                author=author_name 
            ).send()