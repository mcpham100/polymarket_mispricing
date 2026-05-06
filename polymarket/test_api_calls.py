import unittest
import inspect
import requests
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_calls

class TestGammaMarkets(unittest.TestCase):

    def test_returns_generator(self):
        result = api_calls.gamma_markets()
        self.assertTrue(inspect.isgenerator(result))

    def test_first_page_is_list(self):
        gen = api_calls.gamma_markets()
        page = next(gen)
        self.assertIsInstance(page, list)
        self.assertGreater(len(page), 0)

    def test_tuple_has_eight_fields(self):
        gen = api_calls.gamma_markets()
        page = next(gen)
        for market in page:
            self.assertEqual(len(market), 8)

    def test_tokens_is_list_of_two(self):
        gen = api_calls.gamma_markets()
        page = next(gen)
        for market in page:
            tokens = market[7]
            self.assertIsInstance(tokens, list)
            self.assertEqual(len(tokens), 2)

    def test_field_types(self):
        gen = api_calls.gamma_markets()
        page = next(gen)
        for market in page:
            self.assertIsInstance(market[0], str)   # market_id
            self.assertIsInstance(market[1], str)   # question
            # category is None, skip
            self.assertIsNotNone(market[3])          # liquidity
            self.assertIsNotNone(market[4])          # volume
            self.assertIsNotNone(market[5])          # spread

    def test_pagination_yields_multiple_pages(self):
        gen = api_calls.gamma_markets()
        pages = []
        for i, page in enumerate(gen):
            pages.append(page)
            if i >= 1:
                break
        self.assertGreater(len(pages), 1)

    def test_no_duplicate_market_ids_within_page(self):
        gen = api_calls.gamma_markets()
        page = next(gen)
        ids = [market[0] for market in page]
        self.assertEqual(len(ids), len(set(ids)))


class TestClobMidpoints(unittest.TestCase):

    def setUp(self):
        # grab real tokens from gamma for live tests
        gen = api_calls.gamma_markets()
        page = next(gen)
        self.tokens = [market[7] for market in page[:3]]  # use first 3 markets
        self.yes_token = self.tokens[0][0]
        self.no_token = self.tokens[0][1]

    def test_returns_dict(self):
        result = api_calls.clob_midpoints(self.tokens)
        self.assertIsInstance(result, dict)

    def test_returns_nonempty(self):
        result = api_calls.clob_midpoints(self.tokens)
        self.assertGreater(len(result), 0)

    def test_keys_match_token_ids(self):
        result = api_calls.clob_midpoints(self.tokens)
        self.assertIn(self.yes_token, result)
        self.assertIn(self.no_token, result)

    def test_prices_convertible_to_float(self):
        result = api_calls.clob_midpoints(self.tokens)
        for token_id, price in result.items():
            self.assertIsInstance(float(price), float)

    def test_prices_between_zero_and_one(self):
        result = api_calls.clob_midpoints(self.tokens)
        for token_id, price in result.items():
            self.assertGreaterEqual(float(price), 0.0)
            self.assertLessEqual(float(price), 1.0)

    def test_yes_no_sum_near_one(self):
        result = api_calls.clob_midpoints(self.tokens)
        yes = float(result.get(self.yes_token, 0))
        no = float(result.get(self.no_token, 0))
        self.assertAlmostEqual(yes + no, 1.0, delta=0.05)

    def test_returns_empty_dict_on_bad_token(self):
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException("error")
            result = api_calls.clob_midpoints([("bad_token_1", "bad_token_2")])
            self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()