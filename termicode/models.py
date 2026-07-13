OPENROUTER_MODEL_STATS = {
    "qwen/qwen3-coder": {"cost_per_m": 0.0, "tier": "free_coding"},
    "cohere/north-mini-code:free": {"cost_per_m": 0.0, "tier": "free_coding"},
    "poolside/laguna-xs-2.1:free": {"cost_per_m": 0.0, "tier": "free_coding"},
    "meta-llama/llama-3.3-70b-instruct": {"cost_per_m": 0.0, "tier": "free_general"},
    "google/gemma-4-31b-it": {"cost_per_m": 0.0, "tier": "free_general"},
    "openai/gpt-oss-120b": {"cost_per_m": 0.0, "tier": "free_general"},
    "nvidia/nemotron-nano-9b-v2:free": {"cost_per_m": 0.0, "tier": "free_small"},
    "meta-llama/llama-3.2-3b-instruct:free": {"cost_per_m": 0.0, "tier": "free_small"},
    "poolside/laguna-m.1": {"cost_per_m": 0.0, "tier": "free_coding"},
    "poolside/laguna-xs.2": {"cost_per_m": 0.0, "tier": "free_coding"},
    "nvidia/nemotron-3-ultra-550b-a55b": {"cost_per_m": 0.0, "tier": "free_general"},
    "nvidia/nemotron-3-super-120b-a12b": {"cost_per_m": 0.0, "tier": "free_general"},
    "nousresearch/hermes-3-llama-3.1-405b": {"cost_per_m": 0.0, "tier": "free_general"},
    "qwen/qwen3-next-80b-a3b-instruct": {"cost_per_m": 0.0, "tier": "free_general"},
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": {"cost_per_m": 0.0, "tier": "free_general"},
    "tencent/hy3": {"cost_per_m": 0.0, "tier": "free_general"},
    "google/gemma-4-26b-a4b-it": {"cost_per_m": 0.0, "tier": "free_general"},
    "cognitivecomputations/dolphin-mistral-24b-venice-edition": {"cost_per_m": 0.0, "tier": "free_general"},
    "openrouter/free": {"cost_per_m": 0.0, "tier": "free_general"},
    "liquid/lfm-2.5-1.2b-thinking": {"cost_per_m": 0.0, "tier": "free_small"},
    "liquid/lfm-2.5-1.2b-instruct": {"cost_per_m": 0.0, "tier": "free_small"},
    "nvidia/nemotron-3-nano-30b-a3b": {"cost_per_m": 0.0, "tier": "free_small"},
    "openai/gpt-oss-20b": {"cost_per_m": 0.0, "tier": "free_small"},
    "nvidia/nemotron-nano-12b-v2-vl": {"cost_per_m": 0.0, "tier": "free_small"},
    "nvidia/nemotron-3.5-content-safety": {"cost_per_m": 0.0, "tier": "free_small"},
    "anthropic/claude-haiku-4.5": {"cost_per_m": 3.0, "tier": "premium"},
    "kwaipilot/kat-coder-pro-v2": {"cost_per_m": 0.75, "tier": "premium"},
    "openai/gpt-5.4-mini": {"cost_per_m": 2.6, "tier": "premium"},
}


def get_token_usage(tokens: int, model: str) -> tuple:
    """Returns (tokens_used, estimated_cost)."""
    stats = OPENROUTER_MODEL_STATS.get(model, {"cost_per_m": 0.50})
    estimated_cost = (tokens / 1_000_000) * stats["cost_per_m"]
    return tokens, estimated_cost


def route_model(user_prompt: str, current_model: str, model_stats: dict, user_manually_selected: bool, context_length: int = 0) -> str:
    """Routes user prompts to appropriate models based on task complexity and context length."""
    if user_manually_selected:
        return current_model

    prompt_lower = user_prompt.lower()
    use_small_models = context_length <= 10

    coding_keywords = [
        "refactor", "implement", "architecture", "design", "optimize",
        "rewrite", "restructure", "improve", "fix bug", "debug",
        "add feature", "create function", "build", "develop", "integrate",
        "code", "programming", "function", "class", "algorithm",
        "test", "api", "endpoint", "database", "query",
    ]

    simple_keywords = [
        "read", "list", "show", "what is", "explain", "describe",
        "find", "search", "locate", "get", "display", "print",
        "tell me", "what does", "how do i", "help me understand",
    ]

    for keyword in coding_keywords:
        if keyword in prompt_lower:
            coding_models = [m for m, stats in model_stats.items() if stats.get("tier") == "free_coding"]
            if coding_models:
                return coding_models[0]

    for keyword in simple_keywords:
        if keyword in prompt_lower:
            general_models = [m for m, stats in model_stats.items() if stats.get("tier") == "free_general"]
            if general_models:
                return general_models[0]
            if use_small_models:
                small_models = [m for m, stats in model_stats.items() if stats.get("tier") == "free_small"]
                if small_models:
                    return small_models[0]

    coding_models = [m for m, stats in model_stats.items() if stats.get("tier") == "free_coding"]
    if coding_models:
        return coding_models[0]

    general_models = [m for m, stats in model_stats.items() if stats.get("tier") == "free_general"]
    if general_models:
        return general_models[0]

    return "qwen/qwen3-coder"
