#!/usr/bin/env python3
"""
Token Cleanup Script - Immediate fix for excessive refresh tokens
Run this script to clean up your current 300+ refresh tokens
"""

from datetime import datetime, timedelta
from sqlmodel import Session, select
from db import engine
from models import RefreshToken

def cleanup_existing_tokens():
    """Clean up existing refresh tokens - immediate fix"""
    print("🧹 Starting refresh token cleanup...")
    
    with Session(engine) as session:
        # Get current stats
        total_before = len(session.exec(select(RefreshToken)).all())
        print(f"📊 Total tokens before cleanup: {total_before}")
        
        # Delete expired tokens
        expired_tokens = session.exec(
            select(RefreshToken).where(RefreshToken.expires_at < datetime.utcnow())
        ).all()
        expired_count = len(expired_tokens)
        
        for token in expired_tokens:
            session.delete(token)
        
        # Delete old inactive tokens (older than 7 days)
        old_inactive = session.exec(
            select(RefreshToken).where(
                RefreshToken.is_active == False,
                RefreshToken.created_at < datetime.utcnow() - timedelta(days=7)
            )
        ).all()
        inactive_count = len(old_inactive)
        
        for token in old_inactive:
            session.delete(token)
        
        # For each user, keep only the 2 most recent active tokens
        users_with_tokens = session.exec(
            select(RefreshToken.user_id).distinct()
        ).all()
        
        tokens_trimmed = 0
        for user_id in users_with_tokens:
            user_tokens = session.exec(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_active == True
                ).order_by(RefreshToken.created_at.desc())
            ).all()
            
            # If user has more than 2 active tokens, delete the excess
            if len(user_tokens) > 2:
                excess_tokens = user_tokens[2:]  # Keep first 2, delete rest
                for token in excess_tokens:
                    session.delete(token)
                    tokens_trimmed += 1
        
        session.commit()
        
        # Get final stats
        total_after = len(session.exec(select(RefreshToken)).all())
        
        print(f"✅ Cleanup completed!")
        print(f"🗑️  Expired tokens deleted: {expired_count}")
        print(f"🗑️  Old inactive tokens deleted: {inactive_count}")
        print(f"🗑️  Excess active tokens deleted: {tokens_trimmed}")
        print(f"📊 Total tokens after cleanup: {total_after}")
        print(f"📉 Total tokens removed: {total_before - total_after}")
        
        return {
            "tokens_before": total_before,
            "tokens_after": total_after,
            "expired_deleted": expired_count,
            "inactive_deleted": inactive_count,
            "excess_deleted": tokens_trimmed,
            "total_deleted": total_before - total_after
        }

if __name__ == "__main__":
    try:
        result = cleanup_existing_tokens()
        print("\n🎉 Cleanup successful! Your refresh token table is now clean.")
        print("💡 The improved auth system will prevent this buildup in the future.")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        print("🔍 Please check your database connection and try again.")
