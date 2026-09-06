import csv
import json
import tempfile
import unittest
from pathlib import Path

from extractor import EXTRACTION_FIELDS, save_members


class FakeUser:
    def __init__(
        self,
        user_id,
        access_hash=None,
        first_name=None,
        last_name=None,
        username=None,
        bot=False,
    ):
        self.id = user_id
        self.access_hash = access_hash
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.bot = bot


class FakeSource:
    id = -1001234567890
    title = 'Grupo A'


class TestExtractor(unittest.TestCase):
    def test_save_members_writes_reusable_json_and_csv_schema(self):
        users = [
            FakeUser(1, 111, 'João', 'Silva', 'joao', False),
            FakeUser(2, 222, 'Bot', None, 'bot_teste', True),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            json_path, csv_path, records = save_members(users, FakeSource(), tmp)

            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(csv_path).exists())
            self.assertEqual(list(records[0].keys()), EXTRACTION_FIELDS)
            self.assertFalse(records[0]['bot'])
            self.assertTrue(records[1]['bot'])
            self.assertEqual(records[0]['source_group_id'], FakeSource.id)
            self.assertEqual(records[0]['source_group_title'], FakeSource.title)
            self.assertTrue(records[0]['extracted_at'])

            json_records = json.loads(Path(json_path).read_text(encoding='utf-8'))
            self.assertEqual(json_records, records)

            with Path(csv_path).open('r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, EXTRACTION_FIELDS)
                csv_records = list(reader)

            self.assertEqual(len(csv_records), 2)
            self.assertEqual(csv_records[0]['user_id'], '1')
            self.assertEqual(csv_records[0]['username'], 'joao')


if __name__ == '__main__':
    unittest.main()
