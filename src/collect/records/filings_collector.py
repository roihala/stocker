import hashlib
import logging
import os
from typing import List

import arrow
from abc import ABC, abstractmethod

import requests
from cryptography.fernet import Fernet
from google.cloud import storage
from retry import retry

from src.collect.collector_base import CollectorBase
from src.common.otcm import REQUIRED_HEADERS

logger = logging.getLogger('CollectRecords')

try:
    import fitz
except Exception:
    logger.warning("Couldn't import fitz")


PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')


class FilingsCollector(CollectorBase, ABC):
    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'
    DEFAULT_BUCKET_NAME = 'stocker_filings'
    FERNET_KEY = b'BfqGQUtcS573dG6C49Qr1pz71EuXv3YwlboVyUHIHy0='

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bucket_name = self.DEFAULT_BUCKET_NAME + '-dev' if self._debug else self.DEFAULT_BUCKET_NAME
        self._storage_bucket = storage.Client().bucket(self.DEFAULT_BUCKET_NAME + '-dev' if self._debug else self.DEFAULT_BUCKET_NAME)
        self.fernet = Fernet(self.FERNET_KEY)

    @property
    @abstractmethod
    def filing_base_url(self):
        # This url must contain {id} format string
        pass

    @retry(tries=3, delay=0.5)
    def upload_filing(self, record_id, pdf_path):
        blob = f"{hashlib.md5(str.encode(self.name)).hexdigest()}/{self.fernet.encrypt(str.encode(str(record_id))).decode()}"
        self._storage_bucket.blob(blob).upload_from_filename(pdf_path)
        return self.CLOUD_STORAGE_BASE_PATH.format(bucket=self.bucket_name, blob=blob)

    @retry(tries=3, delay=0.5)
    def download_filing(self, record_id, response=None):
        response = response if response else requests.get(self.filing_base_url.format(id=record_id), headers=REQUIRED_HEADERS)
        if not response.ok:
            logger.warning(f"Couldn't get pdf from {response.request.url}, status code: {response.status_code}")
            return ''
        pdf_path = os.path.join(PDF_DIR, self.name, f"{record_id}.pdf")

        # Creating if not exist
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        return pdf_path

    def decorate_diff(self, diff, *args, **kwargs):
        diff = super().decorate_diff(diff)
        diff.update({
            "cloud_path": kwargs['cloud_path'],
            "record_id": kwargs['record_id'],
            'diff_type': 'add',
            'changed_key': 'filings'
        })

        return diff

    @staticmethod
    def _get_pages_from_pdf(pdf_path) -> List[str]:
        pages = []

        with fitz.open(pdf_path, filetype="pdf") as doc:
            for page_number in range(0, doc.pageCount):
                pages.append(" ".join(doc[page_number].getText().split()))

        return pages
