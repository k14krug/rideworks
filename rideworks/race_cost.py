"""Versioned standard-tier estimate; this is not a billing statement."""

from decimal import Decimal


PRICING_VERSION = 'openai-gpt-6-luna-standard-2026-11-06'
PRICING_URL = 'https://developers.openai.com/api/docs/models/gpt-6-luna'
INPUT_RATE = Decimal('0.10')
CACHED_RATE = Decimal('0.01')
CACHE_WRITE_RATE = Decimal('0.125')
OUTPUT_RATE = Decimal('0.50')
MILLION = Decimal(1_000_000)


def estimate_cost(attempts):
    total = Decimal(0)
    included = 0
    for attempt in attempts:
        usage = attempt.get('usage')
        if attempt.get('model') != 'gpt-6-luna' or attempt.get('service_tier') != 'default' or not isinstance(usage, dict):
            continue
        details = usage.get('input_tokens_details')
        if not isinstance(details, dict):
            continue
        numbers = [usage.get('input_tokens'), usage.get('output_tokens'),
                   details.get('cached_tokens'), details.get('cache_write_tokens')]
        if any(type(number) is not int or number < 0 for number in numbers):
            continue
        input_tokens, output_tokens, cached_tokens, cache_writes = numbers
        if cached_tokens + cache_writes > input_tokens:
            continue
        input_multiplier = 2 if input_tokens > 272_000 else 1
        output_multiplier = Decimal('1.5') if input_tokens > 272_000 else Decimal(1)
        total += ((input_tokens - cached_tokens - cache_writes) * INPUT_RATE * input_multiplier
                  + cached_tokens * CACHED_RATE * input_multiplier
                  + cache_writes * CACHE_WRITE_RATE * input_multiplier
                  + output_tokens * OUTPUT_RATE * output_multiplier) / MILLION
        included += 1
    state = 'complete' if included and included == len(attempts) else 'partial' if included else 'unavailable'
    return {'state': state, 'amount_usd': total if included else None,
            'included': included, 'attempted': len(attempts), 'pricing_version': PRICING_VERSION}
