"""
Background worker for processing queued speech jobs.
Run: python worker.py
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import db_session
from app.core.logging import configure_logging
from app.core.models import AudioAsset, JobStatus, ProcessingJob, Speech, SpeechStatus
from app.services.speech_service import _process_audio_speech

logger = logging.getLogger("khatib.worker")

POLL_INTERVAL_SECONDS = 3


def process_one_job() -> bool:
    """Process a single queued job. Returns True if a job was processed."""
    with db_session() as db:
        job = db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.status == JobStatus.queued)
            .order_by(ProcessingJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()

        if job is None:
            return False

        job.status = JobStatus.processing
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        speech = db.get(Speech, job.speech_id)
        if speech is None:
            job.status = JobStatus.dead_letter
            job.last_error = "Speech not found"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return True

        asset = None
        if speech.audio_asset_id:
            asset = db.get(AudioAsset, speech.audio_asset_id)

        try:
            if asset:
                _process_audio_speech(db, speech, asset)
            else:
                speech.status = SpeechStatus.failed
                speech.failure_reason = "No audio asset attached"
                db.commit()

            job.status = JobStatus.completed
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Job %s completed for speech %s", job.id, speech.id)

        except Exception as exc:
            logger.exception("Job %s failed", job.id)
            job.last_error = str(exc)[:2000]
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.dead_letter
                speech.status = SpeechStatus.failed
                speech.failure_reason = "پردازش پس از چند تلاش ناموفق بود."
            else:
                job.status = JobStatus.failed_retryable
            job.finished_at = datetime.now(timezone.utc)
            db.commit()

        return True


def main() -> None:
    configure_logging(settings.debug)
    logger.info("Worker starting (poll every %ds)", POLL_INTERVAL_SECONDS)

    while True:
        try:
            processed = process_one_job()
            if not processed:
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
