from langfuse import get_client, observe, propagate_attributes

__all__ = ["observe", "get_client", "propagate_attributes", "traced_chat"]


def traced_chat(client, name: str, model: str, messages: list, **kwargs):
    """Call client.chat.completions.create inside a Langfuse generation span.

    aisuite hides the underlying provider SDK, so Langfuse's OpenAI drop-in
    can't see these calls; this records model, input, output and token usage.
    """
    params = {k: v for k, v in kwargs.items() if k in ("temperature", "max_tokens")}
    with get_client().start_as_current_observation(
        name=name,
        as_type="generation",
        model=model,
        input=messages,
        model_parameters=params,
    ) as gen:
        resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
        usage = getattr(resp, "usage", None)
        gen.update(
            output=resp.choices[0].message.content,
            usage_details=(
                {
                    "input": getattr(usage, "prompt_tokens", 0),
                    "output": getattr(usage, "completion_tokens", 0),
                }
                if usage
                else None
            ),
        )
        return resp
