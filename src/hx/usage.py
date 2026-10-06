"""Provider-reported usage, without double-counting cached input or inventing cost."""
def usage_breakdown(usage):
    def count(name):
        value = usage.get(name) if isinstance(usage, dict) else None
        return value if type(value) is int and value >= 0 else None

    incoming, outgoing = count('input_tokens'), count('output_tokens')
    cached = count('cached_input_tokens')
    valid_cache = cached is not None and incoming is not None and cached <= incoming
    return {
        'input_tokens': incoming, 'output_tokens': outgoing,
        'cached_input_tokens': cached if valid_cache else None,
        'uncached_input_tokens': incoming - cached if valid_cache else None,
        'reported_tokens': incoming + outgoing if incoming is not None and outgoing is not None else None,
        'usage_known': incoming is not None and outgoing is not None,
        'cache_usage_known': valid_cache,
        'monetary_cost': None,
    }
