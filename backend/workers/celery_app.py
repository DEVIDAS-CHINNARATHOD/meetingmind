"""
workers/celery_app.py — Phase 4
All task modules registered: upload pipeline, face recognition, bots.
"""
from celery import Celery
from config.settings import settings

celery_app = Celery(
    "meetingmind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks",
        "workers.face_tasks",
        "workers.bot_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.tasks.process_meeting":                   {"queue": "ai"},
        "workers.tasks.rename_speaker":                    {"queue": "ai"},
        "workers.tasks.generate_report":                   {"queue": "reports"},
        "workers.face_tasks.run_face_recognition_task":    {"queue": "ai"},
        "workers.face_tasks.extract_faces_for_enrollment": {"queue": "ai"},
        "workers.bot_tasks.join_zoom_meeting":             {"queue": "bots"},
        "workers.bot_tasks.join_google_meet":              {"queue": "bots"},
        "workers.bot_tasks.finalize_live_meeting":         {"queue": "ai"},
    },
    task_time_limit=14400,
    task_soft_time_limit=14100,
    result_expires=86400,
)
