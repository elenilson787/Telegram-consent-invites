import csv
from pathlib import Path
from datetime import datetime


class ReportWriter:
    def __init__(self, directory='logs'):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path = Path(directory) / datetime.now().strftime('migration_%Y%m%d_%H%M%S.csv')
        self.file = self.path.open('w', newline='', encoding='utf-8-sig')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['timestamp', 'user_id', 'username', 'nome', 'status', 'motivo'])
        self.file.flush()

    def write(self, user_id, username, name, status, reason=''):
        self.writer.writerow([datetime.now().astimezone().isoformat(timespec='seconds'), user_id, username or '', name or '', status, reason])
        self.file.flush()

    def close(self):
        if not self.file.closed:
            self.file.close()
