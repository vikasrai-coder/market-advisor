-- User Notification Preferences: Personal Telegram & alert configuration per user
-- Allows users to receive target hit, stop loss hit, and bearish warning alerts to their personal Telegram chat

CREATE TABLE IF NOT EXISTS user_notification_preferences (
  user_id text PRIMARY KEY,
  telegram_chat_id text,
  notify_target_hit boolean DEFAULT true,
  notify_stopped_out boolean DEFAULT true,
  notify_bearish_warning boolean DEFAULT true,
  notify_new_signal boolean DEFAULT false,
  notify_modes text[] DEFAULT ARRAY['swing', 'intraday'],
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE user_notification_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read user_notification_preferences" ON user_notification_preferences FOR SELECT USING (true);
CREATE POLICY "service write user_notification_preferences" ON user_notification_preferences FOR ALL USING (true) WITH CHECK (true);
