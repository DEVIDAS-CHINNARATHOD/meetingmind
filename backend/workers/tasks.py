"""
workers/tasks.py  — Phase 2 (replaces Phase 1)
Upload → Extract → Transcribe → Diarize → Summarize → MoM → Embed → Store
"""
from __future__ import annotations
import asyncio, shutil, tempfile, uuid
from pathlib import Path
import structlog
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from workers.celery_app import celery_app

log = structlog.get_logger(__name__)

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def _fmt(s: float) -> str:
    m, s = divmod(int(s), 60); h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

@celery_app.task(bind=True, name="workers.tasks.process_meeting",
                 max_retries=2, default_retry_delay=30, acks_late=True)
def process_meeting(self: Task, meeting_id: str, workspace_id: str) -> dict:
    log.info("pipeline_start", meeting_id=meeting_id, phase=2)
    self.update_state(state="STARTED", meta={"step":"initializing","progress":2})
    tmp_dir = None
    try:
        from db.database import AsyncSessionLocal
        from models.orm import (ActionItem as AI, Meeting, MeetingStatus,
                                Participant, Report, ReportType, TranscriptSegment)
        from ai.transcription.ffmpeg import extract_audio, get_duration_seconds
        from ai.transcription.whisper import transcribe_audio
        from ai.diarization.pyannote import (diarize_audio,
                                             assign_speakers_to_transcript,
                                             compute_speaker_stats)
        from ai.summarization.groq_llm import generate_summary, generate_mom
        from ai.embeddings.chroma import embed_meeting
        from services.storage import get_storage
        from sqlalchemy import select

        storage = get_storage()

        async def _fetch():
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(Meeting).where(Meeting.id==uuid.UUID(meeting_id)))
                return r.scalar_one_or_none()

        meeting = _run(_fetch())
        if not meeting:
            return {"error":"Meeting not found"}

        async def _set(status, error=None, **kw):
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(Meeting).where(Meeting.id==uuid.UUID(meeting_id)))
                m = r.scalar_one(); m.status = status
                if error: m.processing_error = error[:500]
                for k,v in kw.items(): setattr(m,k,v)
                await db.commit()

        _run(_set(MeetingStatus.PROCESSING))
        self.update_state(state="PROGRESS", meta={"step":"downloading","progress":5})

        tmp_dir = tempfile.mkdtemp(prefix="mm_")
        ext = Path(meeting.original_filename or "rec.mp4").suffix
        tmp_input = str(Path(tmp_dir)/f"original{ext}")
        local = _run(storage.get_local_path(meeting.file_key))
        if local != tmp_input: shutil.copy2(local, tmp_input)
        dur_probe = get_duration_seconds(tmp_input)

        self.update_state(state="PROGRESS", meta={"step":"extracting_audio","progress":12})
        tmp_audio = str(Path(tmp_dir)/"audio.wav")
        extract_audio(tmp_input, tmp_audio)
        with open(tmp_audio,"rb") as f:
            akey = f"workspaces/{workspace_id}/meetings/{meeting_id}/audio.wav"
            _run(storage.upload_file(f, akey, "audio/wav"))

        _run(_set(MeetingStatus.TRANSCRIBING))
        self.update_state(state="PROGRESS", meta={"step":"transcribing","progress":25})
        wr = transcribe_audio(tmp_audio)
        raw_segs = [{"text":s.text,"start_time":s.start,"end_time":s.end,
                     "confidence":s.confidence,"segment_index":i,
                     "speaker_label":None,"speaker_name":None}
                    for i,s in enumerate(wr.segments)]

        self.update_state(state="PROGRESS", meta={"step":"diarizing","progress":40})
        speaker_stats: dict = {}
        try:
            dr = diarize_audio(tmp_audio)
            raw_segs = assign_speakers_to_transcript(raw_segs, dr)
            speaker_stats = compute_speaker_stats(raw_segs)
            log.info("diarized", speakers=dr.num_speakers)
        except Exception as e:
            log.warning("diarization_skipped", reason=str(e)[:120])

        _run(_set(MeetingStatus.SUMMARIZING))
        self.update_state(state="PROGRESS", meta={"step":"summarizing","progress":55})
        sr = generate_summary(wr.full_text, title=meeting.title)

        self.update_state(state="PROGRESS", meta={"step":"generating_mom","progress":68})
        pnames = list(speaker_stats.keys()) if speaker_stats else []
        mr = generate_mom(wr.full_text, meeting.title, pnames, _fmt(wr.duration_seconds))

        self.update_state(state="PROGRESS", meta={"step":"embedding","progress":80})
        chunks = embed_meeting(meeting_id, meeting.title, workspace_id, raw_segs)

        self.update_state(state="PROGRESS", meta={"step":"saving","progress":92})
        async def _persist():
            async with AsyncSessionLocal() as db:
                r = await db.execute(select(Meeting).where(Meeting.id==uuid.UUID(meeting_id)))
                m = r.scalar_one()
                m.transcript=wr.full_text; m.summary=sr.summary; m.mom=mr.markdown
                m.key_decisions=sr.key_decisions; m.topics=sr.topics
                m.language=wr.language; m.word_count=wr.word_count
                m.duration_seconds=wr.duration_seconds or dur_probe
                m.audio_extracted_key=akey; m.status=MeetingStatus.COMPLETED
                for seg in raw_segs:
                    db.add(TranscriptSegment(meeting_id=m.id,
                        speaker_label=seg.get("speaker_label"),
                        speaker_name=seg.get("speaker_name"),
                        text=seg["text"], start_time=seg["start_time"],
                        end_time=seg["end_time"], confidence=seg.get("confidence"),
                        segment_index=seg["segment_index"]))
                for label, stats in speaker_stats.items():
                    db.add(Participant(meeting_id=m.id, name=label,
                        speaker_label=label,
                        talk_time_seconds=stats["talk_time_seconds"],
                        word_count=stats["word_count"]))
                for item in sr.action_items:
                    db.add(AI(meeting_id=m.id, task=item.task,
                        assigned_to=item.assigned_to,
                        deadline=item.deadline, priority=item.priority))
                db.add(Report(meeting_id=m.id, report_type=ReportType.MOM, format="md"))
                await db.commit()

        _run(_persist())
        if tmp_dir: shutil.rmtree(tmp_dir, ignore_errors=True)
        log.info("pipeline_complete", meeting_id=meeting_id,
                 speakers=len(speaker_stats), words=wr.word_count, chunks=chunks)
        return {"meeting_id":meeting_id,"status":"completed",
                "duration_seconds":wr.duration_seconds,
                "num_speakers":len(speaker_stats),"word_count":wr.word_count,
                "action_items":len(sr.action_items),"chunks_embedded":chunks}

    except SoftTimeLimitExceeded:
        _run(_set(MeetingStatus.FAILED, error="Processing timed out"))
        return {"error":"timed_out"}
    except Exception as exc:
        log.exception("pipeline_failed", meeting_id=meeting_id)
        try: _run(_set(MeetingStatus.FAILED, error=str(exc)[:500]))
        except Exception: pass
        if tmp_dir: shutil.rmtree(tmp_dir, ignore_errors=True)
        raise self.retry(exc=exc)


@celery_app.task(name="workers.tasks.generate_report", max_retries=2)
def generate_report(meeting_id: str, report_type: str, fmt: str, workspace_id: str) -> dict:
    from sqlalchemy import select
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, Report, ReportType
    from services.storage import get_storage, make_report_key
    from services.report_generator import generate_pdf_mom, generate_docx_mom

    async def _inner():
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(Meeting).where(Meeting.id==uuid.UUID(meeting_id)))
            m = r.scalar_one_or_none()
            if not m or not m.mom: raise ValueError("Meeting not found or MoM missing")
            if fmt=="pdf": b=generate_pdf_mom(m.title,m.mom,m.created_at); ct="application/pdf"
            elif fmt=="docx": b=generate_docx_mom(m.title,m.mom); ct="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else: raise ValueError(f"Bad fmt {fmt}")
            key = make_report_key(workspace_id, meeting_id, report_type, fmt)
            await get_storage().upload_bytes(b, key, ct)
            db.add(Report(meeting_id=m.id, report_type=ReportType(report_type),
                          file_key=key, file_size_bytes=len(b), format=fmt))
            await db.commit()
            return {"key":key,"size":len(b)}

    return _run(_inner())


@celery_app.task(name="workers.tasks.rename_speaker", max_retries=1)
def rename_speaker(meeting_id: str, speaker_label: str, new_name: str, workspace_id: str) -> dict:
    from sqlalchemy import select, update as su
    from db.database import AsyncSessionLocal
    from models.orm import Meeting, Participant, TranscriptSegment
    from ai.embeddings.chroma import embed_meeting

    async def _rename():
        async with AsyncSessionLocal() as db:
            await db.execute(su(TranscriptSegment)
                .where(TranscriptSegment.meeting_id==uuid.UUID(meeting_id),
                       TranscriptSegment.speaker_label==speaker_label)
                .values(speaker_name=new_name))
            await db.execute(su(Participant)
                .where(Participant.meeting_id==uuid.UUID(meeting_id),
                       Participant.speaker_label==speaker_label)
                .values(name=new_name))
            await db.commit()
            r = await db.execute(select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id==uuid.UUID(meeting_id))
                .order_by(TranscriptSegment.segment_index))
            segs = r.scalars().all()
            mr = await db.execute(select(Meeting).where(Meeting.id==uuid.UUID(meeting_id)))
            mtitle = mr.scalar_one().title
            return ([{"text":s.text,"speaker_label":s.speaker_label,
                      "speaker_name":s.speaker_name,"start_time":s.start_time,
                      "end_time":s.end_time} for s in segs], mtitle)

    segs, title = _run(_rename())
    n = embed_meeting(meeting_id, title, workspace_id, segs)
    log.info("speaker_renamed", label=speaker_label, name=new_name, chunks=n)
    return {"chunks_reembedded":n}
