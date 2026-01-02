import asyncio
import logging
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.error import Forbidden, RetryAfter
import database as db
import api_client
import formatter
import registries
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def execute_schedule(bot: Bot, schedule_id: int, manual_trigger: bool = False, admin_user_id: int = None, target_all: bool = False):
    """
    Executes a forecast schedule: fetches data and sends to subscribers.
    """
    # 1. Load Schedule details
    schedules = db.get_all_schedules()
    schedule = next((s for s in schedules if s['id'] == schedule_id), None)
    
    if not schedule:
        logger.error(f"Schedule {schedule_id} not found.")
        if manual_trigger and admin_user_id:
            await bot.send_message(admin_user_id, "Error: Schedule ID not found.")
        return

    # 2. Determine Targets
    if manual_trigger and not target_all:
        # Send only to admin
        recipients = [admin_user_id] if admin_user_id else []
        logger.info(f"Manual run for Schedule {schedule_id}, sending to admin {admin_user_id}")
    else:
        # Standard run or Manual 'all'
        recipients = db.get_active_subscribers_chat_ids()
        logger.info(f"Run for Schedule {schedule_id}, sending to {len(recipients)} subscribers")

    if not recipients:
        logger.info("No recipients. Skipping execution.")
        return

    # 3. Check Persistence (Deduplication) - ONLY for scheduled runs
    now_utc = datetime.utcnow()
    date_str = now_utc.strftime("%Y-%m-%d")
    time_str = schedule['time_utc'] # HH:MM
    
    run_id = None
    if not manual_trigger:
        if not db.should_run_schedule(schedule_id, date_str, time_str):
            logger.info(f"Schedule {schedule_id} already ran for {date_str} {time_str}. Skipping.")
            return

        run_id = db.start_run_record(schedule_id, date_str, time_str)
        if run_id is None:
            logger.info(f"Could not lock run for schedule {schedule_id}. Race condition or already exists.")
            return

    # Validation (Post-Lock)
    # We validate after locking to ensure we record the error state for this run, avoiding infinite retry loops if restarting.
    validation_error = None
    
    # 1. Language
    if not registries.validate_language(schedule['language']):
        validation_error = f"Invalid language: {schedule['language']}"

    # 2. Countries
    raw_countries = [c.strip() for c in schedule['countries'].split(',')]
    valid_countries = []
    if not validation_error:
        for c in raw_countries:
            norm = registries.normalize_country_code(c)
            if norm:
                valid_countries.append(norm)
            else:
                # We can either fail partially or strictly. Prompt: "every country code... must exist"
                validation_error = f"Invalid country code: {c}"
                break
    
    if validation_error:
        logger.error(f"Schedule {schedule_id} validation failed: {validation_error}")
        if run_id:
            db.update_run_result(run_id, "error", error_text=validation_error)
        
        if manual_trigger and admin_user_id:
            await bot.send_message(admin_user_id, f"Validation Error: {validation_error}")
        
        # Notify admins
        if not manual_trigger:
             for aid in ADMIN_IDS:
                try: 
                    await bot.send_message(aid, f"⚠️ Schedule {schedule_id} Invalid: {validation_error}") 
                except: pass
        return

    countries_str = ",".join(valid_countries)

    # 4. Fetch Data
    try:
        data = await api_client.fetch_forecast(
            countries=countries_str,
            topics=schedule['topics'],
            language=schedule['language'],
            time_horizon=schedule['time_horizon'],
            depth=schedule['depth']
        )
        
        if not data:
            error_msg = "API returned no data or failed."
            logger.error(error_msg)
            if run_id:
                db.update_run_result(run_id, "error", error_text=error_msg)
            if manual_trigger and admin_user_id:
                await bot.send_message(admin_user_id, f"run failed: {error_msg}")
            
            # Notify admins of failure if not manual
            if not manual_trigger:
                for aid in ADMIN_IDS:
                    try:
                        await bot.send_message(aid, f"⚠️ Schedule {schedule_id} failed: API Error.")
                    except:
                        pass
            return

        # 5. Format Messages
        messages = formatter.format_forecast_results(data)
        
        # 6. Send to Recipients (Broadcasting)
        success_count = 0
        
        for chat_id in recipients:
            try:
                for msg in messages:
                    await bot.send_message(chat_id, msg, parse_mode='HTML', disable_web_page_preview=True)
                success_count += 1
                
                # Rate limit handling: sleep slightly between users
                # Telegram limit: 30 msg/sec approx. 
                # If chunked, multiple msgs per user.
                await asyncio.sleep(0.05) 
                
            except Forbidden:
                # User blocked bot
                logger.info(f"User {chat_id} blocked bot. Deactivating.")
                db.unsubscribe_user(chat_id)
            except RetryAfter as e:
                logger.warning(f"Rate limited. Sleeping {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                # Retry once? For now just skip to next to avoid jam.
            except Exception as e:
                logger.error(f"Error sending to {chat_id}: {e}")
        
        status = "success" if success_count > 0 else "partial" # simple logic
        
        if run_id:
            db.update_run_result(run_id, status)
            
        if manual_trigger and admin_user_id:
            await bot.send_message(admin_user_id, f"Run finished. Sent to {success_count} recipients.")

    except Exception as e:
        logger.exception("Critical error in execute_schedule")
        if run_id:
            db.update_run_result(run_id, "error", error_text=str(e))

def setup_scheduler(application, scheduler: AsyncIOScheduler):
    # Load schedules from DB
    schedules = db.get_enabled_schedules()
    
    # Remove existing jobs first?
    scheduler.remove_all_jobs()
    
    count = 0
    for s in schedules:
        try:
            # Parse time HH:MM
            hh, mm = map(int, s['time_utc'].split(':'))
            
            # Add Job
            # We pass 'bot' from application.
            # Warning: application.bot is available.
            
            scheduler.add_job(
                execute_schedule,
                trigger=CronTrigger(hour=hh, minute=mm, timezone="UTC"),
                args=[application.bot, s['id']],
                id=f"schedule_{s['id']}",
                replace_existing=True
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to schedule job {s['id']}: {e}")
            
    logger.info(f"Loaded {count} schedules.")
