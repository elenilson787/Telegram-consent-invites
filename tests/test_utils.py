import unittest
from utils import full_name, random_delay


class FakeUser:
    def __init__(self, first_name=None, last_name=None, username=None, user_id=123):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.id = user_id


class TestUtils(unittest.TestCase):
    def test_full_name(self):
        self.assertEqual(full_name(FakeUser('João', 'Silva')), 'João Silva')

    def test_username_fallback(self):
        self.assertEqual(full_name(FakeUser(username='joao123')), 'joao123')

    def test_id_fallback(self):
        self.assertEqual(full_name(FakeUser(user_id=987)), '987')

    def test_random_delay_range(self):
        for _ in range(100):
            value = random_delay(15, 30)
            self.assertGreaterEqual(value, 15)
            self.assertLessEqual(value, 30)


if __name__ == '__main__':
    unittest.main()
