"""Synthetic pricing examples with no network or private input."""

from decimal import Decimal
import unittest

from rideworks.race_cost import estimate_cost


def attempt(input_tokens=1_000_000, output_tokens=100_000, cached_tokens=100_000, cache_write_tokens=200_000):
    return {'model': 'gpt-6-luna', 'service_tier': 'default',
            'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens,
                      'input_tokens_details': {'cached_tokens': cached_tokens, 'cache_write_tokens': cache_write_tokens},
                      'output_tokens_details': {'reasoning_tokens': 90_000}}}


class CostTests(unittest.TestCase):
    def test_cache_writes_long_context_and_reasoning_not_double_counted(self):
        result = estimate_cost([attempt()])
        expected = (Decimal('700000') * Decimal('.10') * 2
                    + Decimal('100000') * Decimal('.01') * 2
                    + Decimal('200000') * Decimal('.125') * 2
                    + Decimal('100000') * Decimal('.50') * Decimal('1.5')) / Decimal(1_000_000)
        self.assertEqual(result['amount_usd'], expected)
        self.assertEqual(result['state'], 'complete')

    def test_failed_or_unknown_attempts_never_look_complete(self):
        good = attempt(input_tokens=1000, output_tokens=10, cached_tokens=100, cache_write_tokens=200)
        for missing in ({'model': 'gpt-6-luna'}, attempt(cached_tokens=9999999),
                        dict(good, model='unknown'), dict(good, service_tier='priority')):
            result = estimate_cost([good, missing])
            self.assertEqual(result['state'], 'partial')
            self.assertEqual((result['included'], result['attempted']), (1, 2))
        self.assertEqual(estimate_cost([{}])['state'], 'unavailable')
        self.assertIsNone(estimate_cost([{}])['amount_usd'])


if __name__ == '__main__':
    unittest.main()
