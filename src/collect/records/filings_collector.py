import hashlib
import logging
import os
from typing import List

import arrow
from abc import ABC, abstractmethod

import requests
from google.cloud import storage

from src.collect.collector_base import CollectorBase

logger = logging.getLogger('RecordsCollect')

try:
    import fitz
except Exception:
    logger.warning("Couldn't import fitz")


PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'pdfs')


class FilingsCollector(CollectorBase, ABC):
    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'
    DEFAULT_BUCKET_NAME = 'stocker_filings'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bucket_name = self.DEFAULT_BUCKET_NAME + '-dev' if self._debug else self.DEFAULT_BUCKET_NAME
        self._storage_bucket = storage.Client().bucket(self.DEFAULT_BUCKET_NAME + '-dev' if self._debug else self.DEFAULT_BUCKET_NAME)

    @property
    @abstractmethod
    def filing_base_url(self):
        # This url must contain {id} format string
        pass

    def upload_filing(self, ticker, pdf_path):
        blob = f"{hashlib.md5(str.encode(self.name)).hexdigest()}/{ticker}/{arrow.utcnow().timestamp}"
        self._storage_bucket.blob(blob).upload_from_filename(pdf_path)
        return self.CLOUD_STORAGE_BASE_PATH.format(bucket=self.bucket_name, blob=blob)

    def get_pdf(self, record_id, response=None):
        response = response if response else requests.get(self.filing_base_url.format(id=record_id))
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
