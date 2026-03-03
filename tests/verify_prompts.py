import asyncio
from cradle.core.config_manager import global_config
from cradle.selrena.soul import PersonaManager

async def verify_persona_prompt():
    print("Verifying PersonaConfig loading and Prompt Generation...")
    
    # Initialize config (this loads from yaml files)
    sys_cfg = global_config.get_system() # Just checks loading
    # PersonaConfig is loaded via global_config.get_persona() usually?
    # No, usually passed to generator or loaded from specific path.
    # Let's see how SystemPromptGenerator is used.
    
    # Assuming SystemPromptGenerator uses global_config or takes config
    soul_config = global_config.get_soul()
    persona_config = soul_config.persona
    
    manager = PersonaManager(persona_config)
    prompt = manager.build_system_prompt()
    
    if "content" in prompt and ("Selrena" in prompt["content"] or "月见" in prompt["content"]):
        print("SUCCESS: Prompt generated successfully.")
    else:
        print("WARNING: Prompt generated but might be missing keywords.")
    
    print(f"Prompt length: {len(prompt)}")

if __name__ == "__main__":
    asyncio.run(verify_persona_prompt())
