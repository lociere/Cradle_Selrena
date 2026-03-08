import asyncio
from selrena.core.config_manager import global_config
from selrena.persona.profile import PersonaManager

async def verify_persona_prompt():
    print("Verifying PersonaConfig loading and Prompt Generation...")
    
    # Initialize config (this loads from yaml files)
    sys_cfg = global_config.get_system() # Just checks loading
    # current brain/persona configuration
    brain_cfg = global_config.get_brain()
    persona_config = brain_cfg.persona
    
    manager = PersonaManager(persona_config)
    prompt = manager.build_system_prompt()
    
    if "content" in prompt and ("Selrena" in prompt["content"] or brain_cfg.persona.get('name','') in prompt["content"]):
        print("SUCCESS: Prompt generated successfully.")
    else:
        print("WARNING: Prompt generated but might be missing keywords.")
    
    print(f"Prompt length: {len(prompt)}")

if __name__ == "__main__":
    asyncio.run(verify_persona_prompt())
